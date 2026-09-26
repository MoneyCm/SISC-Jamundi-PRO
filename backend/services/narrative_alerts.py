"""Alertas Narrativas: las tres variaciones más significativas del periodo y el estado de los
compromisos del Consejo, en un mensaje de máximo seis líneas listo para WhatsApp.

Uso interno. Nada lo redacta la IA: cada frase sale de una plantilla y de la evidencia guardada
con el mensaje. Una variación significativa pide mirar el dato; no mide riesgo ni causas.

Datos: hechos únicos de la sábana policial (un hecho por identidad, la entrega más reciente
gana). Los periodos terminan en el corte de la última entrega, no en la fecha de hoy.
"""
from __future__ import annotations

import calendar
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

RULES_VERSION = "2026.09"
TZ = ZoneInfo("America/Bogota")

ALPHA = 0.05
MIN_TOTAL = 6  # hechos entre los dos periodos
MIN_DIFFERENCE = {"SEMANAL": 3, "MENSUAL": 5}
BASELINE_PERIODS = 4
SMALL_BASE = 30  # por debajo, no se dan porcentajes (misma regla del informe al Consejo)
MAX_SELECTED = 3
MAX_PER_DIMENSION = 2
DUE_SOON_DAYS = 15
MAX_LINES = 6
MAX_CHARS = 1200

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
    {"code": "PERIODOS", "title": "Qué se compara",
     "text": "Semanal: los 7 días que terminan en el corte de la última sábana policial, frente a los 7 días anteriores. "
             "Mensual: el último mes completo dentro del corte, frente al mes anterior. Ambos periodos se leen de la "
             "misma entrega, así que los registros tardíos afectan a los dos por igual."},
    {"code": "PRUEBA", "title": "Cuándo una variación es significativa",
     "text": "Si nada hubiera cambiado, los hechos de los dos periodos se repartirían según su duración. Se calcula la "
             "probabilidad de un reparto tan desigual (prueba binomial condicional) y debe ser menor al 5 %. Además: al "
             "menos 6 hechos entre los dos periodos y una diferencia de al menos 3 hechos (semanal) o 5 (mensual)."},
    {"code": "REBOTE", "title": "No es un rebote",
     "text": "El cambio debe sostenerse frente al promedio de los 4 periodos anteriores: subir desde una semana "
             "atípicamente baja hasta lo normal no cuenta como alza."},
    {"code": "ORDEN", "title": "Cuáles se eligen",
     "text": "Primero las alzas, luego las bajas; dentro de cada grupo, la menor probabilidad y luego la mayor "
             "diferencia. Máximo 2 de las 3 en la misma dimensión (delito, barrio, franja). Si hay menos de 3, el "
             "mensaje lo dice y no rellena."},
    {"code": "COMPROMISOS", "title": "Compromisos",
     "text": "Vencido: abierto y con plazo pasado. Próximo a vencer: abierto y con plazo en los 15 días siguientes. "
             "Cumplido: pasó a cumplido en los últimos 7 días (semanal) o 30 (mensual). Un compromiso se relaciona con "
             "una variación si su texto o territorio nombra el barrio, el delito o la franja."},
    {"code": "LIMITES", "title": "Qué no dice",
     "text": "Con muchas comparaciones, algunas variaciones serán azar: la evidencia dice cuántas se esperan y cuáles "
             "superan el umbral estricto (Bonferroni). Solo cuenta hechos conocidos por la Policía."},
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
    return prefix + " ".join(word if index and word in LOWER_WORDS else word.capitalize()
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


def period_label(frequency: str, start: date, end: date) -> str:
    if frequency == "MENSUAL":
        return f"{MONTHS[start.month - 1]} de {start.year}"
    if start.month == end.month:
        return f"{start.day} al {day_month(end)}"
    return f"{day_month(start)} al {day_month(end)}"


def previous_label(frequency: str, start: date) -> str:
    return "la semana anterior" if frequency == "SEMANAL" else MONTHS[start.month - 1]


# ---------------------------------------------------------------- periodos

def month_bounds(year: int, month: int) -> Tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def periods(frequency: str, cutoff: date) -> Dict[str, Any]:
    if frequency == "SEMANAL":
        current = (cutoff - timedelta(days=6), cutoff)
        shifted = lambda back: (current[0] - timedelta(days=7 * back), current[1] - timedelta(days=7 * back))
        return {"current": current, "previous": shifted(1),
                "baseline": [shifted(back) for back in range(1, BASELINE_PERIODS + 1)]}
    if frequency != "MENSUAL":
        raise ValueError(f"Frecuencia desconocida: {frequency}")
    year, month = cutoff.year, cutoff.month
    if cutoff != month_bounds(year, month)[1]:  # el mes del corte aún no está completo
        year, month = shift_month(year, month, -1)
    return {"current": month_bounds(year, month), "previous": month_bounds(*shift_month(year, month, -1)),
            "baseline": [month_bounds(*shift_month(year, month, -back)) for back in range(1, BASELINE_PERIODS + 1)]}


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
             place_ok: Callable[[str], bool] = lambda name: True) -> Dict[str, Any]:
    """Prueba cada categoría de cada dimensión y elige las variaciones más significativas."""
    keys = {
        "DELITO": lambda e: e["conducta"],
        "BARRIO": lambda e: e["lugar"] if e["lugar"] and place_ok(e["lugar"]) else None,
        "FRANJA": lambda e: franja_of(e["hora"]),
    }
    current_w, previous_w = plan["current"], plan["previous"]
    share = days(current_w) / (days(current_w) + days(previous_w))
    baseline_days = sum(days(window) for window in plan["baseline"])
    min_difference = MIN_DIFFERENCE[frequency]
    tests: List[Dict[str, Any]] = []
    for dimension, key in keys.items():
        current = _count(events, current_w, key)
        previous = _count(events, previous_w, key)
        baseline: Counter = Counter()
        for window in plan["baseline"]:
            baseline.update(_count(events, window, key))
        for category in sorted(set(current) | set(previous)):
            c, p = current[category], previous[category]
            expected = baseline[category] * days(current_w) / baseline_days if baseline_days else 0.0
            test = {"dimension": dimension, "category": category, "current": c, "previous": p,
                    "difference": c - p, "baseline_expected": round(expected, 1),
                    "p_value": binomial_two_sided(c, p, share)}
            reasons = []
            if c + p < MIN_TOTAL:
                reasons.append("pocos hechos")
            if abs(c - p) < min_difference:
                reasons.append("diferencia pequeña")
            if test["p_value"] >= ALPHA:
                reasons.append("puede ser azar")
            if c != p and (c - expected) * (1 if c > p else -1) < abs(c - p) / 2:
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
        if len(selected) == MAX_SELECTED:
            break
        if per_dimension[test["dimension"]] < MAX_PER_DIMENSION:
            selected.append(test)
            per_dimension[test["dimension"]] += 1
    return {"tests": len(tests), "significant": significant, "selected": selected,
            "expected_by_chance": round(len(tests) * ALPHA, 1), "strict_threshold": strict,
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


def commitment_state(commitment: Dict[str, Any], today: date) -> str:
    """VENCIDO | PROXIMO | ABIERTO | CUMPLIDO | CERRADO."""
    status, deadline = commitment["status"], commitment.get("deadline_date")
    if status == "CUMPLIDO":
        return "CUMPLIDO"
    if status in CLOSED_STATUSES:
        return "CERRADO"
    if deadline and deadline < today:
        return "VENCIDO"
    if deadline and deadline <= today + timedelta(days=DUE_SOON_DAYS):
        return "PROXIMO"
    return "ABIERTO"


def cross_commitments(selected: List[Dict[str, Any]], commitments: List[Dict[str, Any]], today: date,
                      frequency: str) -> Dict[str, Any]:
    window_days = 7 if frequency == "SEMANAL" else 30
    since = today - timedelta(days=window_days - 1)
    states = {c["code"]: commitment_state(c, today) for c in commitments}
    recent_done = [c for c in commitments if states[c["code"]] == "CUMPLIDO" and c.get("fulfilled_on")
                   and since <= c["fulfilled_on"] <= today]
    summary = {
        "overdue": sorted((c["code"] for c in commitments if states[c["code"]] == "VENCIDO")),
        "due_soon": sorted((c["code"] for c in commitments if states[c["code"]] == "PROXIMO")),
        "fulfilled_recent": sorted(c["code"] for c in recent_done),
        "fulfilled_window_days": window_days,
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
    against = f"frente a {previous_label(frequency, previous_start)}"
    name = subject(variation, labels)
    if variation["dimension"] == "DELITO":
        return f"{name} {'subió' if c > p else 'bajó'} de {p} a {_facts(c)}{_pct(variation)} {against}."
    verb = "subieron" if c > p else "bajaron"
    extra = ""
    top = variation.get("top_conducta")
    if variation["dimension"] == "BARRIO" and top and variation["kind"] == "AUMENTO":
        extra = f", sobre todo {labels.get(top, top).lower()}"
    return f"En {name} los hechos {verb} de {p} a {c}{_pct(variation)} {against}{extra}."


def commitments_line(cross: Dict[str, Any]) -> str:
    overdue, due, done = len(cross["overdue"]), len(cross["due_soon"]), len(cross["fulfilled_recent"])
    related_open = {item["code"] for items in cross["related"] for item in items if item["state"] != "CUMPLIDO"}
    parts = [plural(overdue, "vencido", "vencidos"),
             f"{plural(due, 'vence', 'vencen')} en los próximos {DUE_SOON_DAYS} días",
             f"{plural(done, 'cumplido', 'cumplidos')} en los últimos {cross['fulfilled_window_days']} días"]
    line = f"Compromisos del Consejo: {parts[0]}, {parts[1]} y {parts[2]}."
    if related_open:
        line = line[:-1] + f"; {plural(len(related_open), 'abierto se relaciona', 'abiertos se relacionan')} con estas variaciones."
    return line


def action_line(selected: List[Dict[str, Any]], cross: Dict[str, Any], labels: Dict[str, str]) -> Optional[str]:
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
                    f"({', '.join(late[:3])}): se sugiere pedir su avance antes del próximo Consejo.")
    for variation, items in increases:
        if variation["dimension"] in ("DELITO", "BARRIO") and not any(i["state"] != "CUMPLIDO" for i in items):
            return f"{who(variation)} no tiene compromiso abierto del Consejo: se sugiere llevarla a la próxima sesión."
    for variation, items in zip(selected, cross["related"]):
        soon = [item for item in items if item["state"] == "PROXIMO"]
        if soon:
            deadline = date.fromisoformat(soon[0]["deadline_date"])
            return f"El compromiso {soon[0]['code']} ({subject(variation, labels)}) vence el {day_month(deadline)}."
    if cross["overdue"]:
        return "Se sugiere pedir el avance de los compromisos vencidos antes del próximo Consejo."
    return None


def compose(frequency: str, plan: Dict[str, Any], cutoff: date, selected: List[Dict[str, Any]],
            cross: Dict[str, Any], labels: Dict[str, str]) -> str:
    kind = "semanal" if frequency == "SEMANAL" else "mensual"
    lines = [f"*SISC Jamundí · Alerta {kind}* ({period_label(frequency, *plan['current'])}; "
             f"datos policiales al {cutoff:%d/%m/%Y})."]
    lines += [variation_line(v, frequency, plan["previous"][0], labels) for v in selected]
    against = previous_label(frequency, plan["previous"][0])
    if not selected:
        lines.append(f"Ninguna variación por delito, barrio u horario es significativa frente a {against}.")
    elif len(selected) < MAX_SELECTED:
        lines.append(f"No hubo otras variaciones significativas frente a {against}.")
    lines.append(commitments_line(cross))
    action = action_line(selected, cross, labels)
    if action:
        lines.append(action)
    return "\n".join(lines[:MAX_LINES])


def validate_text(value: str) -> str:
    lines = [line.rstrip() for line in (value or "").strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("El mensaje no puede quedar vacío.")
    if len(lines) > MAX_LINES:
        raise ValueError(f"El mensaje tiene {len(lines)} líneas; el máximo es {MAX_LINES}.")
    result = "\n".join(lines)
    if len(result) > MAX_CHARS:
        raise ValueError(f"El mensaje tiene {len(result)} caracteres; el máximo es {MAX_CHARS}.")
    return result


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


def compute(db: Session, frequency: str, today: Optional[date] = None) -> Dict[str, Any]:
    """Calcula el mensaje sin guardarlo."""
    from api.analitica import _is_publishable_location
    from services.intervention_followup import latest_covering_run

    today = today or datetime.now(TZ).date()
    run = latest_covering_run(db)
    if run is None:
        raise LookupError("No hay una entrega completa de la sábana policial con cobertura declarada.")
    cutoff = run.cobertura_fin
    plan = periods(frequency, cutoff)
    result = evaluate(load_events(db), frequency, plan, place_ok=_is_publishable_location)
    cross = cross_commitments(result["selected"], load_commitments(db), today, frequency)
    labels = conducta_labels()
    message = compose(frequency, plan, cutoff, result["selected"], cross, labels)
    iso = lambda window: {"start": window[0].isoformat(), "end": window[1].isoformat()}
    for item in result["significant"]:
        item["label"] = subject(item, labels)
    evidence = {
        "periods": {"current": iso(plan["current"]), "previous": iso(plan["previous"]),
                    "baseline": [iso(window) for window in plan["baseline"]]},
        "totals": result["totals"], "tests": result["tests"], "expected_by_chance": result["expected_by_chance"],
        "strict_threshold": result["strict_threshold"], "significant": result["significant"][:15],
        "selected": result["selected"], "commitments": cross, "as_of": today.isoformat(),
    }
    return {"frequency": frequency, "plan": plan, "cutoff": cutoff, "source_version_id": str(run.id),
            "text": message, "evidence": evidence}


def generate(db: Session, frequency: str, username: str, trigger: str = "MANUAL",
             today: Optional[date] = None):
    """Genera y guarda el mensaje del periodo. Si ya existe para la misma entrega, lo devuelve."""
    from db.models_narrative_alerts import NarrativeAlert, NarrativeAlertRevision

    data = compute(db, frequency, today)
    plan = data["plan"]
    existing = db.query(NarrativeAlert).filter(
        NarrativeAlert.frequency == frequency, NarrativeAlert.period_end == plan["current"][1],
        NarrativeAlert.source_version_id == data["source_version_id"]).first()
    if existing:
        return existing, False
    alert = NarrativeAlert(
        frequency=frequency, period_start=plan["current"][0], period_end=plan["current"][1],
        previous_start=plan["previous"][0], previous_end=plan["previous"][1], data_cutoff=data["cutoff"],
        source_version_id=data["source_version_id"], rules_version=RULES_VERSION, trigger=trigger,
        generated_text=data["text"], text=data["text"], status="BORRADOR", evidence=data["evidence"],
        version=0, created_by=username, updated_by=username,
    )
    db.add(alert)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()  # otro proceso lo generó al mismo tiempo
        return db.query(NarrativeAlert).filter(
            NarrativeAlert.frequency == frequency, NarrativeAlert.period_end == plan["current"][1],
            NarrativeAlert.source_version_id == data["source_version_id"]).one(), False
    db.add(NarrativeAlertRevision(alert_id=alert.id, version=0, action="GENERADO", text=alert.text, username=username))
    # Una entrega corregida del mismo periodo reemplaza los borradores anteriores (los enviados se quedan).
    for old in db.query(NarrativeAlert).filter(
            NarrativeAlert.frequency == frequency, NarrativeAlert.period_end == plan["current"][1],
            NarrativeAlert.id != alert.id, NarrativeAlert.status == "BORRADOR").all():
        old.status, old.superseded_by, old.version = "REEMPLAZADO", alert.id, old.version + 1
        old.updated_by = username
        db.add(NarrativeAlertRevision(alert_id=old.id, version=old.version, action="REEMPLAZADO", text=old.text,
                                      note="Una entrega policial más reciente generó otra versión.", username=username))
    db.commit()
    db.refresh(alert)
    return alert, True


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


def _transition(db: Session, alert_id: str, expected_version: int, username: str, action: str,
                new_text: Optional[str] = None, note: Optional[str] = None):
    from db.models_narrative_alerts import NarrativeAlertRevision

    alert = _get(db, alert_id)
    if alert.version != expected_version:
        raise PermissionError("Otra persona modificó este mensaje. Recárguelo antes de continuar.")
    if alert.status != "BORRADOR":
        raise PermissionError(f"El mensaje está {alert.status.lower()} y ya no se puede cambiar.")
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
    return _transition(db, alert_id, expected_version, username, "EDITADO", validate_text(new_text), note)


def mark_sent(db: Session, alert_id: str, expected_version: int, username: str, note: Optional[str] = None):
    return _transition(db, alert_id, expected_version, username, "ENVIADO", note=note)


def discard(db: Session, alert_id: str, expected_version: int, username: str, note: str):
    if not (note or "").strip():
        raise ValueError("Para descartar un mensaje, diga por qué.")
    return _transition(db, alert_id, expected_version, username, "DESCARTADO", note=note)


def serialize(alert, revisions: Optional[list] = None) -> Dict[str, Any]:
    data = {
        "id": str(alert.id), "frequency": alert.frequency, "status": alert.status, "trigger": alert.trigger,
        "period_start": alert.period_start.isoformat(), "period_end": alert.period_end.isoformat(),
        "previous_start": alert.previous_start.isoformat(), "previous_end": alert.previous_end.isoformat(),
        "period_label": period_label(alert.frequency, alert.period_start, alert.period_end),
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


def run_scheduled(db: Session, now: Optional[datetime] = None) -> List[str]:
    """Genera los mensajes programados que falten desde la última hora programada. Idempotente."""
    from db.models_narrative_alerts import NarrativeAlert

    now = now or datetime.now(TZ)
    created = []
    for frequency in ("SEMANAL", "MENSUAL"):
        since = slot_start(frequency, now)
        done = db.query(NarrativeAlert.id).filter(NarrativeAlert.frequency == frequency,
                                                  NarrativeAlert.created_at >= since).first()
        if done:
            continue
        try:
            alert, new = generate(db, frequency, "SISTEMA", trigger="PROGRAMADA", today=now.astimezone(TZ).date())
        except LookupError:
            continue
        if new:
            created.append(f"{frequency}:{alert.period_end.isoformat()}")
    return created
