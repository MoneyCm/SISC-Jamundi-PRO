"""Alertas Narrativas: las variaciones más significativas del periodo, el estado de los compromisos
del Consejo y lo que aportan otras fuentes, en un mensaje corto listo para WhatsApp.

Cinco tipos: semanal (6 líneas), mensual (10), para el Consejo de Seguridad (12), semestral (12)
y anual (15). Uso interno. Nada lo redacta la IA: cada frase sale de una plantilla y de la
evidencia guardada con el mensaje. Una variación significativa pide mirar el dato; no mide riesgo
ni causas.

Datos: hechos únicos de la sábana policial (un hecho por identidad, la entrega más reciente
gana). Los periodos terminan en el corte de la última entrega, no en la fecha de hoy. Otra fuente
solo entra si su dato cubre el periodo y si tiene algo que decir, y siempre con su fecha.
"""
from __future__ import annotations

import calendar
import logging
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.entrega_vigente import filtro_sql

logger = logging.getLogger("narrative_alerts")

RULES_VERSION = "2026.09b"
TZ = ZoneInfo("America/Bogota")

ALPHA = 0.05
MIN_TOTAL = 6  # hechos entre los dos periodos
BASELINE_PERIODS = 4
SMALL_BASE = 30  # por debajo, no se dan porcentajes (misma regla del informe al Consejo)
MAX_PER_DIMENSION = 2
DUE_SOON_DAYS = 15
CHARS_PER_LINE = 200
COUNCIL_WINDOW = 28
STALE_DAYS = 10
MIN_CELL = 5

TYPES: Dict[str, Dict[str, Any]] = {
    "SEMANAL": {"label": "Semanal", "title": "Alerta semanal", "max_lines": 6, "max_variations": 3, "min_difference": 3},
    "MENSUAL": {"label": "Mensual", "title": "Alerta mensual", "max_lines": 10, "max_variations": 4, "min_difference": 5},
    "CONSEJO": {"label": "Consejo de Seguridad", "title": "Alerta para el Consejo de Seguridad", "max_lines": 12,
                "max_variations": 4, "min_difference": 5},
    "SEMESTRAL": {"label": "Semestral", "title": "Balance semestral", "max_lines": 12, "max_variations": 5, "min_difference": 8},
    "ANUAL": {"label": "Anual", "title": "Balance anual", "max_lines": 15, "max_variations": 5, "min_difference": 10},
}
FREQUENCIES = tuple(TYPES)
# Compatibilidad: límites del mensaje semanal.
MAX_LINES = TYPES["SEMANAL"]["max_lines"]
MAX_CHARS = MAX_LINES * CHARS_PER_LINE
MIN_DIFFERENCE = {code: config["min_difference"] for code, config in TYPES.items()}


def max_lines(frequency: str) -> int:
    return TYPES[frequency]["max_lines"]


def max_chars(frequency: str) -> int:
    return max_lines(frequency) * CHARS_PER_LINE


DIMENSIONS = {"DELITO": "tipo de delito", "BARRIO": "barrio o vereda", "FRANJA": "franja horaria"}
FRANJAS = [  # las cuatro franjas de la propia fuente policial (INTERVALOS_HORA)
    ("MADRUGADA", 0, "la madrugada", "00:00 a 05:59"),
    ("MANANA", 6, "la mañana", "06:00 a 11:59"),
    ("TARDE", 12, "la tarde", "12:00 a 17:59"),
    ("NOCHE", 18, "la noche", "18:00 a 23:59"),
]
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")
CLOSED_STATUSES = {"CUMPLIDO", "NO_CUMPLIDO", "DESCARTADO"}
COUNCIL = "CONSEJO_SEGURIDAD"
AT_GROUPS = {"AT", "SECTOR_AT"}

# Palabras que relacionan un compromiso con un delito o una franja (texto sin tildes, en mayúsculas).
CONDUCTA_KEYWORDS = {
    "HOMICIDIO": ["HOMICID", "ASESINAT", "SICARI", "MUERTE VIOLENTA"],
    "HURTO_PERSONAS": ["HURTO A PERSONA", "HURTO CALLEJERO", "ATRACO", "RAPONAZO", "CELULAR"],
    "HURTO_VEHICULOS": ["HURTO DE MOTO", "HURTO DE VEHICUL", "HURTO A VEHICUL", "HURTO DE AUTOMOTOR", "HURTO A AUTOMOTOR"],
    "HURTO_COMERCIO": ["HURTO A COMERCIO", "HURTO AL COMERCIO", "HURTO DE COMERCIO", "ESTABLECIMIENTOS COMERCIALES"],
    "HURTO_RESIDENCIAS": ["HURTO A RESIDENCI", "HURTO DE RESIDENCI", "HURTO A VIVIENDA", "HURTO EN VIVIENDA"],
    "LESIONES": ["LESION", "RINA", "AGRESION"],
    "EXTORSION": ["EXTORSI"],
    "VIF": ["VIOLENCIA INTRAFAMILIAR", "VIF", "VIOLENCIA DE GENERO"],
    "SECUESTRO": ["SECUESTR"],
    "TRAFICO": ["MICROTRAFICO", "ESTUPEFACIENTE", "EXPENDIO", "DROGA"],
}
FRANJA_KEYWORDS = {"MADRUGADA": ["MADRUGADA", "NOCTURN"], "NOCHE": ["NOCHE", "NOCTURN"], "MANANA": [], "TARDE": []}
PLACE_PREFIXES = r"^(CGTO|CORREGIMIENTO|VDA|VEREDA|BARRIO|URB|URBANIZACION|CONJUNTO RES\.?|CONJUNTO RESIDENCIAL|CONJ\.?)\s+"
LOWER_WORDS = {"de", "del", "la", "las", "los", "el", "y", "en"}

RULES = [
    {"code": "TIPOS", "title": "Tipos de alerta y qué comparan",
     "text": "Semanal (6 líneas): los 7 días al corte de la última sábana frente a los 7 anteriores. Mensual (10): el último "
             "mes completo frente al anterior. Consejo de Seguridad (12): los últimos 28 días frente a los 28 anteriores. "
             "Semestral (12) y anual (15): el último semestre o año completo frente al mismo periodo del año anterior. "
             "Ambos periodos se leen de la misma entrega, así que los registros tardíos afectan a los dos por igual."},
    {"code": "PRUEBA", "title": "Cuándo una variación es significativa",
     "text": "Si nada hubiera cambiado, los hechos de los dos periodos se repartirían según su duración. Se calcula la "
             "probabilidad de un reparto tan desigual (prueba binomial condicional) y debe ser menor al 5 %. Además: al "
             "menos 6 hechos entre los dos periodos y una diferencia mínima de 3 hechos (semanal), 5 (mensual y Consejo), "
             "8 (semestral) o 10 (anual)."},
    {"code": "REBOTE", "title": "No es un rebote",
     "text": "El cambio debe sostenerse frente al promedio de los 4 periodos anteriores con datos: subir desde un periodo "
             "atípicamente bajo hasta lo normal no cuenta como alza."},
    {"code": "ORDEN", "title": "Cuáles se eligen",
     "text": "Primero las alzas, luego las bajas; dentro de cada grupo, la menor probabilidad y luego la mayor diferencia. "
             "Hasta 3 variaciones (semanal), 4 (mensual y Consejo) o 5 (semestral y anual), con máximo 2 de la misma "
             "dimensión. Si hay menos, el mensaje lo dice y no rellena."},
    {"code": "COMPROMISOS", "title": "Compromisos",
     "text": "Vencido: abierto y con plazo pasado. Próximo a vencer: abierto y con plazo en los 15 días siguientes (en la "
             "alerta del Consejo, antes de la sesión). Cumplidos: en los últimos 7 días (semanal), 30 (mensual), desde el "
             "Consejo anterior (Consejo) o dentro del periodo (semestral y anual). Un compromiso se relaciona con una "
             "variación si su texto o territorio nombra el barrio, el delito o la franja."},
    {"code": "FUENTES", "title": "Otras fuentes",
     "text": "Alertas Tempranas de la Defensoría: se marca la variación de un barrio advertido y, salvo en la semanal, se "
             "resume la zona de la AT 005-24 con sus conductas advertidas. Medicina Legal: solo si ya cubre meses del "
             "periodo (llega con uno a tres meses de rezago), como cifra preliminar. Comisarías de Familia: casos de "
             "violencia intrafamiliar si sus bases cubren el periodo. Señales estadísticas altas (alerta del Consejo) y "
             "portal ciudadano, solo si hay algo que reportar. Si no caben, se omiten primero las del final."},
    {"code": "LIMITES", "title": "Qué no dice",
     "text": "Con muchas comparaciones, algunas variaciones serán azar: la evidencia dice cuántas se esperan y cuáles "
             "superan el umbral estricto (Bonferroni). La sábana solo cuenta hechos conocidos por la Policía."},
]


# ---------------------------------------------------------------- utilidades de texto

def normalize(value: Optional[str]) -> str:
    value = unicodedata.normalize("NFD", str(value or "").upper())
    return re.sub(r"\s+", " ", "".join(c for c in value if unicodedata.category(c) != "Mn")).strip()


def place_label(name: str) -> str:
    """BONANZA → Bonanza; CGTO EL GUABAL → corregimiento El Guabal; SACHAMATE (URB MUNICIPAL) → Sachamate."""
    name = re.sub(r"\(.*?\)", " ", name.strip().upper()).strip()
    prefix = ""
    if re.match(r"^CGTO\s+", name):
        prefix, name = "corregimiento ", re.sub(r"^CGTO\s+", "", name)
    words = name.lower().split()
    cap = lambda word: re.sub(r"(^|[/\-])(\w)", lambda m: m.group(1) + m.group(2).upper(), word)
    return prefix + " ".join(word if index and word in LOWER_WORDS else cap(word)
                             for index, word in enumerate(words))


def place_core(name: str) -> str:
    """Nombre del lugar sin prefijos ni paréntesis, para buscarlo en el texto de un compromiso."""
    core = re.sub(r"\(.*?\)", " ", normalize(name))
    core = re.sub(PLACE_PREFIXES, "", core).strip()
    return re.sub(r"\s+", " ", core)


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def day_month(value: date) -> str:
    return f"{value.day} de {MONTHS[value.month - 1]}"


def _semester_name(start: date) -> str:
    return f"{'primer' if start.month <= 6 else 'segundo'} semestre de {start.year}"


def period_label(frequency: str, start: date, end: date) -> str:
    if frequency == "MENSUAL":
        return f"{MONTHS[start.month - 1]} de {start.year}"
    if frequency == "SEMESTRAL":
        return _semester_name(start)
    if frequency == "ANUAL":
        return str(start.year)
    if start.month == end.month:
        return f"{start.day} al {day_month(end)}"
    return f"{day_month(start)} al {day_month(end)}"


def against(frequency: str, start: date) -> str:
    """«frente a la semana anterior», «frente al primer semestre de 2025»…"""
    return f"frente a {previous_label(frequency, start)}".replace("frente a el ", "frente al ")


def previous_label(frequency: str, start: date) -> str:
    if frequency == "SEMANAL":
        return "la semana anterior"
    if frequency == "CONSEJO":
        return f"los {COUNCIL_WINDOW} días anteriores"
    if frequency == "SEMESTRAL":
        return f"el {_semester_name(start)}"
    if frequency == "ANUAL":
        return str(start.year)
    return MONTHS[start.month - 1]


# ---------------------------------------------------------------- periodos

def month_bounds(year: int, month: int) -> Tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def semester_bounds(year: int, half: int) -> Tuple[date, date]:
    return (date(year, 1, 1), date(year, 6, 30)) if half == 1 else (date(year, 7, 1), date(year, 12, 31))


def periods(frequency: str, cutoff: date) -> Dict[str, Any]:
    if frequency in ("SEMANAL", "CONSEJO"):
        length = 7 if frequency == "SEMANAL" else COUNCIL_WINDOW
        current = (cutoff - timedelta(days=length - 1), cutoff)
        shifted = lambda back: (current[0] - timedelta(days=length * back), current[1] - timedelta(days=length * back))
        return {"current": current, "previous": shifted(1),
                "baseline": [shifted(back) for back in range(1, BASELINE_PERIODS + 1)]}
    if frequency == "MENSUAL":
        year, month = cutoff.year, cutoff.month
        if cutoff != month_bounds(year, month)[1]:  # el mes del corte aún no está completo
            year, month = shift_month(year, month, -1)
        return {"current": month_bounds(year, month), "previous": month_bounds(*shift_month(year, month, -1)),
                "baseline": [month_bounds(*shift_month(year, month, -back)) for back in range(1, BASELINE_PERIODS + 1)]}
    if frequency == "SEMESTRAL":
        year, half = cutoff.year, 1 if cutoff.month <= 6 else 2
        if cutoff != semester_bounds(year, half)[1]:
            year, half = (year, 1) if half == 2 else (year - 1, 2)
        return {"current": semester_bounds(year, half), "previous": semester_bounds(year - 1, half),
                "baseline": [semester_bounds(year - back, half) for back in range(1, BASELINE_PERIODS + 1)]}
    if frequency == "ANUAL":
        year = cutoff.year if (cutoff.month, cutoff.day) == (12, 31) else cutoff.year - 1
        bounds = lambda y: (date(y, 1, 1), date(y, 12, 31))
        return {"current": bounds(year), "previous": bounds(year - 1),
                "baseline": [bounds(year - back) for back in range(1, BASELINE_PERIODS + 1)]}
    raise ValueError(f"Frecuencia desconocida: {frequency}")


def days(window: Tuple[date, date]) -> int:
    return (window[1] - window[0]).days + 1


# ---------------------------------------------------------------- estadística

def _log_binom_pmf(k: int, n: int, q: float) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(q) + (n - k) * math.log1p(-q)


def binomial_two_sided(current: int, previous: int, share: float = 0.5) -> float:
    """Probabilidad (dos colas) de un reparto tan desigual si ambos periodos tuvieran la misma tasa.

    share: fracción del tiempo total que ocupa el periodo actual.
    """
    n = current + previous
    if n == 0:
        return 1.0
    ks = range(current, n + 1) if current >= n * share else range(0, current + 1)
    tail = sum(math.exp(_log_binom_pmf(k, n, share)) for k in ks)
    return min(1.0, 2 * tail)


def franja_of(hour: Optional[int]) -> Optional[str]:
    if hour is None:
        return None
    for code, start, _, _ in reversed(FRANJAS):
        if hour >= start:
            return code
    return None


def _count(events: Sequence[Dict[str, Any]], window: Tuple[date, date], key: Callable) -> Counter:
    counter: Counter = Counter()
    for event in events:
        if window[0] <= event["fecha"] <= window[1]:
            value = key(event)
            if value:
                counter[value] += 1
    return counter


def evaluate(events: Sequence[Dict[str, Any]], frequency: str, plan: Dict[str, Any],
             place_ok: Callable[[str], bool] = lambda name: True,
             data_start: Optional[date] = None) -> Dict[str, Any]:
    """Prueba cada categoría de cada dimensión y elige las variaciones más significativas.

    data_start: primer día con datos; los periodos de la base anteriores a él no cuentan como ceros.
    """
    keys = {
        "DELITO": lambda e: e["conducta"],
        "BARRIO": lambda e: e["lugar"] if e["lugar"] and place_ok(e["lugar"]) else None,
        "FRANJA": lambda e: franja_of(e["hora"]),
    }
    current_w, previous_w = plan["current"], plan["previous"]
    share = days(current_w) / (days(current_w) + days(previous_w))
    baseline_windows = [w for w in plan["baseline"] if data_start is None or w[0] >= data_start]
    baseline_days = sum(days(window) for window in baseline_windows)
    min_difference = TYPES[frequency]["min_difference"]
    tests: List[Dict[str, Any]] = []
    for dimension, key in keys.items():
        current = _count(events, current_w, key)
        previous = _count(events, previous_w, key)
        baseline: Counter = Counter()
        for window in baseline_windows:
            baseline.update(_count(events, window, key))
        for category in sorted(set(current) | set(previous)):
            c, p = current[category], previous[category]
            expected = baseline[category] * days(current_w) / baseline_days if baseline_days else None
            test = {"dimension": dimension, "category": category, "current": c, "previous": p,
                    "difference": c - p, "baseline_expected": round(expected, 1) if expected is not None else None,
                    "p_value": binomial_two_sided(c, p, share)}
            reasons = []
            if c + p < MIN_TOTAL:
                reasons.append("pocos hechos")
            if abs(c - p) < min_difference:
                reasons.append("diferencia pequeña")
            if test["p_value"] >= ALPHA:
                reasons.append("puede ser azar")
            if expected is not None and c != p and (c - expected) * (1 if c > p else -1) < abs(c - p) / 2:
                reasons.append("rebote frente a los periodos anteriores")
            test["significant"] = not reasons
            test["reasons"] = reasons
            test["kind"] = "AUMENTO" if c > p else "CAIDA" if c < p else "IGUAL"
            if dimension == "BARRIO" and test["significant"]:
                top = _count([e for e in events if e["lugar"] == category], current_w, lambda e: e["conducta"])
                test["top_conducta"] = top.most_common(1)[0][0] if top else None
            tests.append(test)
    strict = ALPHA / len(tests) if tests else ALPHA
    significant = [test for test in tests if test["significant"]]
    for test in significant:
        test["strict"] = test["p_value"] < strict
    significant.sort(key=lambda t: (t["kind"] != "AUMENTO", t["p_value"], -abs(t["difference"])))
    selected, per_dimension = [], Counter()
    for test in significant:
        if len(selected) == TYPES[frequency]["max_variations"]:
            break
        if per_dimension[test["dimension"]] < MAX_PER_DIMENSION:
            selected.append(test)
            per_dimension[test["dimension"]] += 1
    return {"tests": len(tests), "significant": significant, "selected": selected,
            "expected_by_chance": round(len(tests) * ALPHA, 1), "strict_threshold": strict,
            "baseline_periods": len(baseline_windows),
            "totals": {"current": sum(1 for e in events if current_w[0] <= e["fecha"] <= current_w[1]),
                       "previous": sum(1 for e in events if previous_w[0] <= e["fecha"] <= previous_w[1])}}


# ---------------------------------------------------------------- compromisos

def _matches(haystack: str, patterns: Sequence[str]) -> bool:
    return any(re.search(r"\b" + re.escape(pattern), haystack) for pattern in patterns)


def relates(variation: Dict[str, Any], commitment: Dict[str, Any]) -> bool:
    haystack = normalize(" ".join(filter(None, [commitment.get("text"), commitment.get("territory")])))
    haystack = re.sub(r"\bHURTOS\b", "HURTO", haystack)
    if variation["dimension"] == "BARRIO":
        core = place_core(variation["category"])
        return len(core) >= 4 and re.search(r"\b" + re.escape(core) + r"\b", haystack) is not None
    if variation["dimension"] == "DELITO":
        return _matches(haystack, CONDUCTA_KEYWORDS.get(variation["category"], []))
    return _matches(haystack, FRANJA_KEYWORDS.get(variation["category"], []))


def commitment_state(commitment: Dict[str, Any], today: date, due_until: Optional[date] = None) -> str:
    """VENCIDO | PROXIMO | ABIERTO | CUMPLIDO | CERRADO."""
    due_until = due_until or today + timedelta(days=DUE_SOON_DAYS)
    status, deadline = commitment["status"], commitment.get("deadline_date")
    if status == "CUMPLIDO":
        return "CUMPLIDO"
    if status in CLOSED_STATUSES:
        return "CERRADO"
    if deadline and deadline < today:
        return "VENCIDO"
    if deadline and deadline <= due_until:
        return "PROXIMO"
    return "ABIERTO"


def cross_commitments(selected: List[Dict[str, Any]], commitments: List[Dict[str, Any]], today: date,
                      frequency: str, due_until: Optional[date] = None, due_label: Optional[str] = None,
                      fulfilled: Optional[Tuple[date, date, str]] = None) -> Dict[str, Any]:
    """fulfilled: (desde, hasta, texto) de los cumplidos que se cuentan; por defecto, los últimos 7 o 30 días."""
    window_days = 7 if frequency == "SEMANAL" else 30
    if fulfilled is None:
        fulfilled = (today - timedelta(days=window_days - 1), today, f"en los últimos {window_days} días")
    since, until, fulfilled_label = fulfilled
    states = {c["code"]: commitment_state(c, today, due_until) for c in commitments}
    recent_done = [c for c in commitments if states[c["code"]] == "CUMPLIDO" and c.get("fulfilled_on")
                   and since <= c["fulfilled_on"] <= until]
    summary = {
        "overdue": sorted((c["code"] for c in commitments if states[c["code"]] == "VENCIDO")),
        "due_soon": sorted((c["code"] for c in commitments if states[c["code"]] == "PROXIMO")),
        "fulfilled_recent": sorted(c["code"] for c in recent_done),
        "fulfilled_window_days": window_days,
        "fulfilled_label": fulfilled_label,
        "due_label": due_label or f"en los próximos {DUE_SOON_DAYS} días",
        "open": sum(1 for state in states.values() if state in {"VENCIDO", "PROXIMO", "ABIERTO"}),
    }
    related = []
    for variation in selected:
        items = []
        for c in commitments:
            state = states[c["code"]]
            if state == "CERRADO" or (state == "CUMPLIDO" and c not in recent_done):
                continue
            if relates(variation, c):
                items.append({"code": c["code"], "state": state, "responsible": c.get("responsible"),
                              "deadline_date": c["deadline_date"].isoformat() if c.get("deadline_date") else None,
                              "text": (c.get("text") or "")[:160]})
        related.append(items)
    return {**summary, "related": related}


# ---------------------------------------------------------------- redacción

def subject(variation: Dict[str, Any], labels: Dict[str, str]) -> str:
    dimension, category = variation["dimension"], variation["category"]
    if dimension == "DELITO":
        return labels.get(category, category.replace("_", " ").capitalize())
    if dimension == "BARRIO":
        return place_label(category)
    franja = next(item for item in FRANJAS if item[0] == category)
    return f"{franja[2]} ({franja[3]})"


def _facts(count: int) -> str:
    return plural(count, "hecho", "hechos")


def _pct(variation: Dict[str, Any]) -> str:
    c, p = variation["current"], variation["previous"]
    return f" ({(c - p) / p * 100:+.0f} %)" if p >= SMALL_BASE else ""


def variation_line(variation: Dict[str, Any], frequency: str, previous_start: date, labels: Dict[str, str]) -> str:
    c, p = variation["current"], variation["previous"]
    versus = against(frequency, previous_start)
    name = subject(variation, labels)
    if variation["dimension"] == "DELITO":
        return f"{name} {'subió' if c > p else 'bajó'} de {p} a {_facts(c)}{_pct(variation)} {versus}."
    verb = "subieron" if c > p else "bajaron"
    extra = ""
    top = variation.get("top_conducta")
    if variation["dimension"] == "BARRIO" and top and variation["kind"] == "AUMENTO":
        extra = f", sobre todo {labels.get(top, top).lower()}"
    if variation.get("alerta_temprana") and variation["kind"] == "AUMENTO":
        extra += ", en territorio con Alerta Temprana de la Defensoría"
    return f"En {name} los hechos {verb} de {p} a {c}{_pct(variation)} {versus}{extra}."


def commitments_line(cross: Dict[str, Any]) -> str:
    overdue, due, done = len(cross["overdue"]), len(cross["due_soon"]), len(cross["fulfilled_recent"])
    related_open = {item["code"] for items in cross["related"] for item in items if item["state"] != "CUMPLIDO"}
    due_label = cross.get("due_label") or f"en los próximos {DUE_SOON_DAYS} días"
    fulfilled_label = cross.get("fulfilled_label") or f"en los últimos {cross['fulfilled_window_days']} días"
    parts = [plural(overdue, "vencido", "vencidos"), f"{plural(due, 'vence', 'vencen')} {due_label}",
             f"{plural(done, 'cumplido', 'cumplidos')} {fulfilled_label}"]
    line = f"Compromisos del Consejo: {parts[0]}, {parts[1]} y {parts[2]}."
    if related_open:
        line = line[:-1] + f"; {plural(len(related_open), 'abierto se relaciona', 'abiertos se relacionan')} con estas variaciones."
    return line


def action_line(selected: List[Dict[str, Any]], cross: Dict[str, Any], labels: Dict[str, str],
                before: str = "antes del próximo Consejo") -> Optional[str]:
    def who(variation):
        name = subject(variation, labels)
        if variation["dimension"] == "DELITO":
            return f"El alza de {name.lower()}"
        return f"El alza en {name}"

    increases = [(v, items) for v, items in zip(selected, cross["related"]) if v["kind"] == "AUMENTO"]
    for variation, items in increases:
        late = [item["code"] for item in items if item["state"] == "VENCIDO"]
        if late:
            return (f"{who(variation)} tiene {plural(len(late), 'compromiso vencido', 'compromisos vencidos')} "
                    f"({', '.join(late[:3])}): se sugiere pedir su avance {before}.")
    for variation, items in increases:
        if variation["dimension"] in ("DELITO", "BARRIO") and not any(i["state"] != "CUMPLIDO" for i in items):
            session = "en la sesión" if before == "antes de la sesión" else "a la próxima sesión"
            return f"{who(variation)} no tiene compromiso abierto del Consejo: se sugiere llevarla {session}."
    for variation, items in zip(selected, cross["related"]):
        soon = [item for item in items if item["state"] == "PROXIMO"]
        if soon:
            deadline = date.fromisoformat(soon[0]["deadline_date"])
            return f"El compromiso {soon[0]['code']} ({subject(variation, labels)}) vence el {day_month(deadline)}."
    if cross["overdue"]:
        return f"Se sugiere pedir el avance de los compromisos vencidos {before}."
    return None


def header_line(frequency: str, plan: Dict[str, Any], cutoff: date, today: Optional[date] = None,
                occasion_label: Optional[str] = None) -> str:
    current, previous = plan["current"], plan["previous"]
    stale = ""
    if today and frequency in ("SEMANAL", "CONSEJO") and (today - cutoff).days > STALE_DAYS:
        stale = f", con {(today - cutoff).days} días de retraso"
    data = f"datos policiales al {cutoff:%d/%m/%Y}{stale}"
    if frequency == "CONSEJO":
        session = f" · sesión: {occasion_label}" if occasion_label else ""
        return (f"*SISC Jamundí · Alerta para el Consejo de Seguridad*{session}. Últimos {COUNCIL_WINDOW} días "
                f"({period_label(frequency, *current)}); {data}.")
    if frequency == "SEMESTRAL":
        return (f"*SISC Jamundí · Balance semestral* ({period_label(frequency, *current)} frente al mismo semestre de "
                f"{previous[0].year}; {data}).")
    if frequency == "ANUAL":
        return f"*SISC Jamundí · Balance anual* ({current[0].year} frente a {previous[0].year}; {data})."
    kind = "semanal" if frequency == "SEMANAL" else "mensual"
    return f"*SISC Jamundí · Alerta {kind}* ({period_label(frequency, *current)}; {data})."


def compose(frequency: str, plan: Dict[str, Any], cutoff: date, selected: List[Dict[str, Any]],
            cross: Dict[str, Any], labels: Dict[str, str], context: Optional[List[Dict[str, Any]]] = None,
            today: Optional[date] = None, occasion_label: Optional[str] = None) -> str:
    """Encabezado, variaciones, otras fuentes (las que quepan, en orden) y compromisos con la acción sugerida."""
    config = TYPES[frequency]
    lines = [header_line(frequency, plan, cutoff, today, occasion_label)]
    lines += [variation_line(v, frequency, plan["previous"][0], labels) for v in selected]
    versus = against(frequency, plan["previous"][0])
    if not selected:
        lines.append(f"Ninguna variación por delito, barrio u horario es significativa {versus}.")
    elif len(selected) < config["max_variations"]:
        lines.append(f"No hubo otras variaciones significativas {versus}.")
    before = "antes de la sesión" if frequency == "CONSEJO" else "antes del próximo Consejo"
    tail = [commitments_line(cross)]
    action = action_line(selected, cross, labels, before)
    if action:
        tail.append(action)
    room = config["max_lines"] - len(lines) - len(tail)
    extra = [item["line"] for item in (context or [])][:max(room, 0)]
    return "\n".join((lines + extra + tail)[:config["max_lines"]])


def validate_text(value: str, frequency: str = "SEMANAL") -> str:
    limit_lines, limit_chars = max_lines(frequency), max_chars(frequency)
    lines = [line.rstrip() for line in (value or "").strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("El mensaje no puede quedar vacío.")
    if len(lines) > limit_lines:
        raise ValueError(f"El mensaje tiene {len(lines)} líneas; el máximo es {limit_lines}.")
    result = "\n".join(lines)
    if len(result) > limit_chars:
        raise ValueError(f"El mensaje tiene {len(result)} caracteres; el máximo es {limit_chars}.")
    return result


# ---------------------------------------------------------------- otras fuentes

def at_zone_line(events: Sequence[Dict[str, Any]], plan: Dict[str, Any], frequency: str,
                 classify: Callable[[str], Tuple[str, str]], alert: Dict[str, Any],
                 labels: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Hechos de las conductas advertidas en los territorios y corredores de una Alerta Temprana."""
    advised = {item["codigo_siedco"] for item in alert.get("conductas_advertidas", []) if item.get("codigo_siedco")}
    if not advised:
        return None
    in_zone = [e for e in events if e["conducta"] in advised and e["lugar"] and classify(e["lugar"])[0] in AT_GROUPS]
    current = [e for e in in_zone if plan["current"][0] <= e["fecha"] <= plan["current"][1]]
    previous = [e for e in in_zone if plan["previous"][0] <= e["fecha"] <= plan["previous"][1]]
    homicides = sum(1 for e in current if e["conducta"] == "HOMICIDIO")
    places = Counter(classify(e["lugar"])[1] for e in current)
    detail = f", {plural(homicides, 'homicidio', 'homicidios')}" if homicides else ""
    top = places.most_common(1)
    where = f"; más hechos en {top[0][0]} ({top[0][1]})" if top and top[0][1] >= 2 else ""
    line = (f"Zona con Alerta Temprana {alert['numero']} de la Defensoría: {_facts(len(current))} de las conductas "
            f"advertidas ({len(previous)} en {previous_label(frequency, plan['previous'][0])}){detail}{where}.")
    return {"source": "DEFENSORIA_AT", "line": line,
            "detail": {"alert": alert["id"], "current": len(current), "previous": len(previous), "homicides": homicides,
                       "conductas": sorted(advised), "places": dict(places.most_common(5))}}


def medicina_legal_line(db: Session, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Solo si Medicina Legal ya cubre meses del periodo; cifras preliminares frente a los mismos meses del año anterior."""
    from services.medicina_legal_bulletin import PRIVACY_THRESHOLD, indicator_rows

    rows = indicator_rows(db, *plan["current"])
    rows = [row for row in rows if row["start"] >= plan["current"][0]]
    if not rows:
        return None
    label = rows[0]["metadata"]["period_label"]
    value = lambda row, key: ("menos de 3" if row[key] is None and key == "value" else
                              (str(int(row[key])) if row[key] is not None else "menos de 3"))
    homicides = next((row for row in rows if row["code"] == "medicina.homicidios"), None)
    others = [row for row in rows if row["code"] != "medicina.homicidios" and row["value"] is not None
              and row["comparison_value"] is not None]
    others.sort(key=lambda row: -abs(row["value"] - row["comparison_value"]))
    parts = []
    if homicides:
        compared = f" ({int(homicides['comparison_value'])} un año antes)" if homicides["comparison_value"] is not None else ""
        parts.append(f"{value(homicides, 'value')} presuntos homicidios{compared}")
    if others:
        row = others[0]
        parts.append(f"{row['name'].lower()}: {int(row['value'])} ({int(row['comparison_value'])})")
    if not parts:
        return None
    return {"source": "MEDICINA_LEGAL", "line": f"Medicina Legal ({label}, preliminar): {'; '.join(parts)}.",
            "detail": {"period": label, "cutoff": rows[0]["cutoff"].isoformat() if rows[0].get("cutoff") else None,
                       "threshold": PRIVACY_THRESHOLD,
                       "rows": [{"code": r["code"], "value": r["value"], "previous": r["comparison_value"]} for r in rows]}}


def comisarias_line(db: Session, plan: Dict[str, Any], frequency: str) -> Optional[Dict[str, Any]]:
    """Casos de violencia intrafamiliar de las Comisarías, si sus bases cubren el periodo."""
    from sqlalchemy import func
    from db.models_vif import VifCase

    last = db.query(func.max(VifCase.fecha_atencion)).scalar()
    if not last or last < plan["current"][1] - timedelta(days=7):
        return None
    rows = db.query(VifCase.fecha_atencion, VifCase.lugar).filter(
        VifCase.fecha_atencion >= plan["previous"][0], VifCase.fecha_atencion <= plan["current"][1]).all()
    current = [lugar for fecha, lugar in rows if plan["current"][0] <= fecha <= plan["current"][1]]
    previous = [lugar for fecha, lugar in rows if plan["previous"][0] <= fecha <= plan["previous"][1]]
    if not current and not previous:
        return None
    top = Counter(place for place in current if place).most_common(1)
    where = f"; más casos en {place_label(top[0][0])} ({top[0][1]})" if top and top[0][1] >= MIN_CELL else ""
    line = (f"Comisarías de Familia: {plural(len(current), 'caso', 'casos')} de violencia intrafamiliar atendidos "
            f"({len(previous)} en {previous_label(frequency, plan['previous'][0])}){where}.")
    return {"source": "COMISARIAS", "line": line, "detail": {"current": len(current), "previous": len(previous)}}


def signals_line(db: Session, cutoff: date, selected: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Señal estadística alta del radar que no esté ya contada entre las variaciones."""
    from services.anomaly_radar import build_anomalies

    data = build_anomalies(db, cutoff)
    covered = {normalize(item["category"]) for item in selected} | {normalize(subject(item, conducta_labels()))
                                                                     for item in selected}
    for item in data.get("anomalies", []):
        if item["level"] != "ALTA" or item["rule"] == "R3":
            continue
        if normalize(item.get("territory")) in covered or normalize(item.get("conducta")) in covered:
            continue
        return {"source": "SENALES", "line": f"Señal estadística alta: {item['title']} ({item['detail'].split('.')[0].lower()}).",
                "detail": {"rule": item["rule"], "title": item["title"], "p_value": item["p_value"]}}
    return None


def citizens_line(db: Session, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from db.models import SecureReport
    from db.models_panic import PanicAlert

    start = datetime.combine(plan["current"][0], datetime.min.time())
    end = datetime.combine(plan["current"][1] + timedelta(days=1), datetime.min.time())
    reports = db.query(SecureReport.estado).filter(SecureReport.created_at >= start, SecureReport.created_at < end).all()
    panic = db.query(PanicAlert.id).filter(PanicAlert.created_at >= start, PanicAlert.created_at < end).count()
    if not reports and not panic:
        return None
    parts = []
    if reports:
        open_ = sum(1 for (state,) in reports if state != "CERRADO")
        pending = f" ({open_} sin cerrar)" if open_ else ""
        parts.append(f"{plural(len(reports), 'reporte seguro', 'reportes seguros')}{pending}")
    if panic:
        parts.append(f"{plural(panic, 'activación', 'activaciones')} del botón de pánico")
    return {"source": "PORTAL_CIUDADANO", "line": f"Portal ciudadano: {' y '.join(parts)} en el periodo.",
            "detail": {"reports": len(reports), "panic": panic}}


def _safe(builder: Callable[[], Optional[Dict[str, Any]]], name: str) -> Optional[Dict[str, Any]]:
    try:
        return builder()
    except Exception as error:  # una fuente con problemas no detiene la alerta
        logger.warning(f"[Alertas Narrativas] Fuente {name} omitida: {error}")
        return None


# ---------------------------------------------------------------- base de datos

def load_events(db: Session) -> List[Dict[str, Any]]:
    """Un registro por hecho (la entrega más reciente gana), con conducta, lugar y hora."""
    from api.analitica import _canonical_conducta_sql, _canonical_location_sql

    identity = "COALESCE(NULLIF(BTRIM(h.id_fuente), ''), NULLIF(BTRIM(h.fingerprint), ''), h.id::text)"
    location = _canonical_location_sql(
        "COALESCE(NULLIF(BTRIM(h.barrio_normalizado), ''), NULLIF(BTRIM(h.vereda_normalizada), ''), 'SIN DATO')")
    conducta = _canonical_conducta_sql("h.conducta_estandar")
    rows = db.execute(text(f"""
        WITH ranked AS (
            SELECT {identity} AS identity, h.fecha_evento AS fecha, {conducta} AS conducta, {location} AS lugar,
                   EXTRACT(HOUR FROM h.hora_evento)::int AS hora,
                   ROW_NUMBER() OVER (
                       PARTITION BY {identity}
                       ORDER BY r.fecha_fin DESC NULLS LAST, h.fecha_ingesta DESC NULLS LAST
                   ) AS rn
            FROM hechos_seguridad h
            LEFT JOIN ingestion_runs r ON r.id = h.ingestion_id
            WHERE h.fuente_codigo = 'POLICIA_SEMANAL' AND h.fecha_evento IS NOT NULL
            {filtro_sql(db, prefijo="h")}
        )
        SELECT fecha, conducta, lugar, hora FROM ranked WHERE rn = 1
    """)).fetchall()
    return [{"fecha": r.fecha, "conducta": r.conducta, "lugar": r.lugar, "hora": r.hora} for r in rows]


def load_commitments(db: Session) -> List[Dict[str, Any]]:
    from db.models_council import CouncilCommitment, CouncilCommitmentUpdate

    fulfilled = dict(
        db.query(CouncilCommitmentUpdate.commitment_id, CouncilCommitmentUpdate.created_at)
        .filter(CouncilCommitmentUpdate.new_status == "CUMPLIDO")
        .order_by(CouncilCommitmentUpdate.created_at.asc()).all()
    )  # la más reciente gana
    rows = db.query(CouncilCommitment).filter(CouncilCommitment.instance == COUNCIL).all()
    return [{"code": row.code, "status": row.status, "deadline_date": row.deadline_date, "text": row.text,
             "territory": row.territory, "responsible": row.responsible,
             "fulfilled_on": fulfilled[row.id].astimezone(TZ).date() if row.id in fulfilled else None}
            for row in rows]


def conducta_labels() -> Dict[str, str]:
    from api.analitica import CONDUCTA_PUBLIC_LABELS
    return dict(CONDUCTA_PUBLIC_LABELS)


def council_sessions(db: Session, today: date):
    """(anterior, próxima) sesión del Consejo según el calendario operativo."""
    from services.operating_calendar import _council_inputs

    previous, upcoming, *_ = _council_inputs(db, today)
    return previous, upcoming


def compute(db: Session, frequency: str, today: Optional[date] = None,
            occasion: Optional[Tuple[date, str, Optional[date]]] = None) -> Dict[str, Any]:
    """Calcula el mensaje sin guardarlo.

    occasion (solo Consejo): (fecha de la sesión, texto de la sesión, fecha del Consejo anterior).
    """
    from api.analitica import _is_publishable_location
    from services.intervention_followup import latest_covering_run
    from services.sat_radar_service import _classifier, load_registry

    if frequency not in TYPES:
        raise ValueError(f"Tipo de alerta desconocido: {frequency}")
    today = today or datetime.now(TZ).date()
    run = latest_covering_run(db)
    if run is None:
        raise LookupError("No hay una entrega completa de la sábana policial con cobertura declarada.")
    cutoff = run.cobertura_fin
    plan = periods(frequency, cutoff)
    events = load_events(db)
    data_start = min((e["fecha"] for e in events), default=None)
    if data_start is None or data_start > plan["previous"][0]:
        raise LookupError(f"La sábana no tiene datos de {previous_label(frequency, plan['previous'][0])} para comparar.")
    result = evaluate(events, frequency, plan, place_ok=_is_publishable_location, data_start=data_start)
    labels = conducta_labels()

    classify, registry = None, None
    try:
        registry = load_registry()
        classify, _ = _classifier(registry)
        for item in result["selected"]:
            if item["dimension"] == "BARRIO":
                item["alerta_temprana"] = classify(item["category"])[0] in AT_GROUPS
    except Exception as error:
        logger.warning(f"[Alertas Narrativas] Registro de Alertas Tempranas no disponible: {error}")

    occasion_date = occasion_label = None
    due_until = due_label = fulfilled = None
    if frequency == "CONSEJO":
        if occasion is None:
            previous_session, upcoming = council_sessions(db, today)
            occasion = (upcoming.start, upcoming.label, previous_session.start)
        occasion_date, occasion_label, previous_session_date = occasion
        due_until, due_label = occasion_date, "antes de la sesión"
        since = previous_session_date or today - timedelta(days=30)
        fulfilled = (since, today, "desde el Consejo anterior")
    elif frequency in ("SEMESTRAL", "ANUAL"):
        name = period_label(frequency, *plan["current"])
        fulfilled = (plan["current"][0], plan["current"][1], f"en el {name}" if frequency == "SEMESTRAL" else f"en {name}")
    cross = cross_commitments(result["selected"], load_commitments(db), today, frequency,
                              due_until=due_until, due_label=due_label, fulfilled=fulfilled)

    context: List[Dict[str, Any]] = []
    if frequency != "SEMANAL":
        if classify and registry:
            main_alert = next((a for a in registry["alertas"] if a.get("territorios_oficiales")), None)
            if main_alert:
                item = _safe(lambda: at_zone_line(events, plan, frequency, classify, main_alert, labels), "Defensoría")
                if item:
                    context.append(item)
        if frequency == "CONSEJO":
            context.append(_safe(lambda: signals_line(db, cutoff, result["selected"]), "señales"))
        context.append(_safe(lambda: medicina_legal_line(db, plan), "Medicina Legal"))
        context.append(_safe(lambda: comisarias_line(db, plan, frequency), "Comisarías"))
        context.append(_safe(lambda: citizens_line(db, plan), "portal ciudadano"))
        context = [item for item in context if item]

    message = compose(frequency, plan, cutoff, result["selected"], cross, labels, context, today, occasion_label)
    used = set(message.split("\n"))
    for item in context:
        item["included"] = item["line"] in used
    iso = lambda window: {"start": window[0].isoformat(), "end": window[1].isoformat()}
    for item in result["significant"]:
        item["label"] = subject(item, labels)
    evidence = {
        "periods": {"current": iso(plan["current"]), "previous": iso(plan["previous"]),
                    "baseline": [iso(window) for window in plan["baseline"]]},
        "totals": result["totals"], "tests": result["tests"], "expected_by_chance": result["expected_by_chance"],
        "strict_threshold": result["strict_threshold"], "baseline_periods": result["baseline_periods"],
        "significant": result["significant"][:15], "selected": result["selected"], "commitments": cross,
        "context": context, "as_of": today.isoformat(),
        "occasion": {"date": occasion_date.isoformat(), "label": occasion_label} if occasion_date else None,
    }
    return {"frequency": frequency, "plan": plan, "cutoff": cutoff, "source_version_id": str(run.id),
            "text": message, "evidence": evidence, "occasion_date": occasion_date, "occasion_label": occasion_label}


# ---------------------------------------------------------------- guardar y revisar

LOCK_KEY = 5_318_008_101  # un solo proceso genera a la vez (programación, carga y botón)


def _lock(db: Session) -> None:
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_KEY})
    except Exception:  # bases sin bloqueos consultivos (pruebas): se sigue sin bloqueo
        pass


def _same_period(db: Session, frequency: str, period_end: date, occasion_date: Optional[date]):
    from db.models_narrative_alerts import NarrativeAlert

    query = db.query(NarrativeAlert).filter(NarrativeAlert.frequency == frequency)
    if frequency == "CONSEJO":
        return query.filter(NarrativeAlert.occasion_date == occasion_date)
    return query.filter(NarrativeAlert.period_end == period_end)


def generate(db: Session, frequency: str, username: str, trigger: str = "MANUAL",
             today: Optional[date] = None, only_new_period: bool = False,
             occasion: Optional[Tuple[date, str, Optional[date]]] = None):
    """Genera y guarda el mensaje del periodo. Devuelve (alerta, creada).

    - Si ya existe para la misma entrega, lo devuelve.
    - Un periodo (o sesión del Consejo) ya enviado no se vuelve a proponer.
    - only_new_period: solo crea si ese periodo aún no tiene ningún mensaje (cargas y programación).
    """
    from db.models_narrative_alerts import NarrativeAlert, NarrativeAlertRevision
    from services.intervention_followup import latest_covering_run

    _lock(db)
    if only_new_period and frequency != "CONSEJO":
        run = latest_covering_run(db)
        if run is None:
            raise LookupError("No hay una entrega completa de la sábana policial con cobertura declarada.")
        existing_any = _same_period(db, frequency, periods(frequency, run.cobertura_fin)["current"][1], None) \
            .order_by(NarrativeAlert.created_at.desc()).first()
        if existing_any:
            db.commit()
            return existing_any, False
    data = compute(db, frequency, today, occasion)
    plan = data["plan"]
    same = _same_period(db, frequency, plan["current"][1], data["occasion_date"])
    existing = same.filter(NarrativeAlert.source_version_id == data["source_version_id"],
                           NarrativeAlert.status != "REEMPLAZADO").order_by(NarrativeAlert.created_at.desc()).first()
    sent = same.filter(NarrativeAlert.status == "ENVIADO").order_by(NarrativeAlert.sent_at.desc()).first()
    if existing or sent or (only_new_period and same.first()):
        db.commit()
        return existing or sent or same.order_by(NarrativeAlert.created_at.desc()).first(), False
    alert = NarrativeAlert(
        frequency=frequency, period_start=plan["current"][0], period_end=plan["current"][1],
        previous_start=plan["previous"][0], previous_end=plan["previous"][1], data_cutoff=data["cutoff"],
        source_version_id=data["source_version_id"], rules_version=RULES_VERSION, trigger=trigger,
        generated_text=data["text"], text=data["text"], status="BORRADOR", evidence=data["evidence"],
        occasion_date=data["occasion_date"], occasion_label=data["occasion_label"],
        version=0, created_by=username, updated_by=username,
    )
    db.add(alert)
    db.flush()
    db.add(NarrativeAlertRevision(alert_id=alert.id, version=0, action="GENERADO", text=alert.text, username=username))
    # Una entrega corregida del mismo periodo reemplaza los borradores anteriores (los enviados se quedan).
    for old in same.filter(NarrativeAlert.id != alert.id, NarrativeAlert.status == "BORRADOR").all():
        old.status, old.superseded_by, old.version = "REEMPLAZADO", alert.id, old.version + 1
        old.updated_by = username
        db.add(NarrativeAlertRevision(alert_id=old.id, version=old.version, action="REEMPLAZADO", text=old.text,
                                      note="Una entrega policial más reciente generó otra versión.", username=username))
    db.commit()
    db.refresh(alert)
    return alert, True


def generate_after_upload(db: Session, username: str) -> List[str]:
    """Al terminar de cargar una sábana: la semanal con los datos nuevos y la mensual, semestral o anual
    solo si la entrega completa un periodo que aún no tenía mensaje."""
    created = []
    for frequency in ("SEMANAL", "MENSUAL", "SEMESTRAL", "ANUAL"):
        try:
            alert, new = generate(db, frequency, username or "SISTEMA", trigger="CARGA",
                                  only_new_period=frequency != "SEMANAL")
        except LookupError:
            db.rollback()
            continue
        if new:
            created.append(f"{frequency}:{alert.period_end.isoformat()}")
    return created


def _get(db: Session, alert_id: str):
    from db.models_narrative_alerts import NarrativeAlert
    import uuid

    try:
        key = uuid.UUID(str(alert_id))
    except ValueError as error:
        raise LookupError("Mensaje no encontrado.") from error
    alert = db.get(NarrativeAlert, key)
    if alert is None:
        raise LookupError("Mensaje no encontrado.")
    return alert


def _editable(alert, expected_version: int) -> None:
    if alert.version != expected_version:
        raise PermissionError("Otra persona modificó este mensaje. Recárguelo antes de continuar.")
    if alert.status != "BORRADOR":
        raise PermissionError(f"El mensaje está {alert.status.lower()} y ya no se puede cambiar.")


def _transition(db: Session, alert_id: str, expected_version: int, username: str, action: str,
                new_text: Optional[str] = None, note: Optional[str] = None):
    from db.models_narrative_alerts import NarrativeAlertRevision

    alert = _get(db, alert_id)
    _editable(alert, expected_version)
    if new_text is not None:
        alert.text = new_text
    alert.version += 1
    alert.updated_by = username
    if action == "ENVIADO":
        alert.status, alert.sent_by, alert.sent_at, alert.sent_note = "ENVIADO", username, datetime.now(TZ), note
    elif action == "DESCARTADO":
        alert.status = "DESCARTADO"
    db.add(NarrativeAlertRevision(alert_id=alert.id, version=alert.version, action=action, text=alert.text,
                                  note=note, username=username))
    db.commit()
    db.refresh(alert)
    return alert


def edit(db: Session, alert_id: str, new_text: str, expected_version: int, username: str, note: Optional[str] = None):
    alert = _get(db, alert_id)
    return _transition(db, alert_id, expected_version, username, "EDITADO", validate_text(new_text, alert.frequency), note)


def mark_sent(db: Session, alert_id: str, expected_version: int, username: str, note: Optional[str] = None):
    return _transition(db, alert_id, expected_version, username, "ENVIADO", note=note)


def discard(db: Session, alert_id: str, expected_version: int, username: str, note: str):
    if not (note or "").strip():
        raise ValueError("Para descartar un mensaje, diga por qué.")
    return _transition(db, alert_id, expected_version, username, "DESCARTADO", note=note)


def refresh(db: Session, alert_id: str, expected_version: int, username: str):
    """Vuelve a calcular un borrador con la última sábana y el estado actual de los compromisos.

    El texto anterior (con sus ediciones) queda en el historial.
    """
    from db.models_narrative_alerts import NarrativeAlertRevision

    alert = _get(db, alert_id)
    _editable(alert, expected_version)
    occasion = None
    if alert.frequency == "CONSEJO" and alert.occasion_date:
        previous_session, _ = council_sessions(db, alert.occasion_date - timedelta(days=1))
        occasion = (alert.occasion_date, alert.occasion_label, previous_session.start)
    data = compute(db, alert.frequency, None, occasion)
    plan = data["plan"]
    alert.period_start, alert.period_end = plan["current"]
    alert.previous_start, alert.previous_end = plan["previous"]
    alert.data_cutoff, alert.source_version_id = data["cutoff"], data["source_version_id"]
    alert.rules_version, alert.evidence = RULES_VERSION, data["evidence"]
    alert.generated_text = alert.text = data["text"]
    alert.version += 1
    alert.updated_by = username
    db.add(NarrativeAlertRevision(
        alert_id=alert.id, version=alert.version, action="ACTUALIZADO", text=alert.text, username=username,
        note=f"Recalculado con la sábana al {data['cutoff']:%d/%m/%Y} y los compromisos al día."))
    db.commit()
    db.refresh(alert)
    return alert


def serialize(alert, revisions: Optional[list] = None) -> Dict[str, Any]:
    config = TYPES.get(alert.frequency, TYPES["SEMANAL"])
    data = {
        "id": str(alert.id), "frequency": alert.frequency, "type_label": config["label"], "type_title": config["title"],
        "max_lines": config["max_lines"], "max_chars": config["max_lines"] * CHARS_PER_LINE,
        "status": alert.status, "trigger": alert.trigger,
        "period_start": alert.period_start.isoformat(), "period_end": alert.period_end.isoformat(),
        "previous_start": alert.previous_start.isoformat(), "previous_end": alert.previous_end.isoformat(),
        "period_label": period_label(alert.frequency, alert.period_start, alert.period_end),
        "occasion_date": alert.occasion_date.isoformat() if alert.occasion_date else None,
        "occasion_label": alert.occasion_label,
        "data_cutoff": alert.data_cutoff.isoformat(), "source_version_id": alert.source_version_id,
        "rules_version": alert.rules_version, "text": alert.text, "generated_text": alert.generated_text,
        "edited": alert.text != alert.generated_text, "version": alert.version,
        "created_by": alert.created_by, "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "updated_by": alert.updated_by, "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
        "sent_by": alert.sent_by, "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
        "sent_note": alert.sent_note, "superseded_by": str(alert.superseded_by) if alert.superseded_by else None,
    }
    if revisions is not None:
        data["evidence"] = alert.evidence
        data["revisions"] = [{"version": r.version, "action": r.action, "text": r.text, "note": r.note,
                              "username": r.username, "created_at": r.created_at.isoformat() if r.created_at else None}
                             for r in revisions]
    return data


# ---------------------------------------------------------------- programación

def slot_start(frequency: str, now: datetime) -> datetime:
    """Última hora programada: lunes 07:00 (semanal) o día 1 a las 07:00 (mensual), hora de Bogotá."""
    now = now.astimezone(TZ)
    if frequency == "SEMANAL":
        start = (now - timedelta(days=now.weekday())).replace(hour=7, minute=0, second=0, microsecond=0)
        return start if start <= now else start - timedelta(days=7)
    start = now.replace(day=1, hour=7, minute=0, second=0, microsecond=0)
    if start > now:
        year, month = shift_month(now.year, now.month, -1)
        start = start.replace(year=year, month=month)
    return start


def council_due(now: datetime, session_start: date, session_end: date) -> bool:
    """La alerta del Consejo se genera desde las 07:00 del día anterior a la sesión y hasta que termina."""
    now = now.astimezone(TZ)
    trigger_at = datetime.combine(session_start - timedelta(days=1), datetime.min.time(), TZ).replace(hour=7)
    return trigger_at <= now and now.date() <= session_end


def run_scheduled(db: Session, now: Optional[datetime] = None) -> List[str]:
    """Respaldo de la generación al cargar la sábana, y la alerta del día anterior al Consejo. Idempotente."""
    from db.models_narrative_alerts import NarrativeAlert

    now = now or datetime.now(TZ)
    today = now.astimezone(TZ).date()
    created = []
    since = slot_start("SEMANAL", now)
    if not db.query(NarrativeAlert.id).filter(NarrativeAlert.frequency == "SEMANAL",
                                              NarrativeAlert.created_at >= since).first():
        try:
            alert, new = generate(db, "SEMANAL", "SISTEMA", trigger="PROGRAMADA", today=today)
            if new:
                created.append(f"SEMANAL:{alert.period_end.isoformat()}")
        except LookupError:
            db.rollback()
    for frequency in ("MENSUAL", "SEMESTRAL", "ANUAL"):
        try:
            alert, new = generate(db, frequency, "SISTEMA", trigger="PROGRAMADA", today=today, only_new_period=True)
            if new:
                created.append(f"{frequency}:{alert.period_end.isoformat()}")
        except LookupError:
            db.rollback()
    previous_session, upcoming = council_sessions(db, today)
    if council_due(now, upcoming.start, upcoming.end) and not db.query(NarrativeAlert.id).filter(
            NarrativeAlert.frequency == "CONSEJO", NarrativeAlert.occasion_date == upcoming.start).first():
        try:
            alert, new = generate(db, "CONSEJO", "SISTEMA", trigger="PROGRAMADA", today=today,
                                  occasion=(upcoming.start, upcoming.label, previous_session.start))
            if new:
                created.append(f"CONSEJO:{upcoming.start.isoformat()}")
        except LookupError:
            db.rollback()
    return created
