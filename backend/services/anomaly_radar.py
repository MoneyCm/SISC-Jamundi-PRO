"""Radar de señales estadísticas: cifras que se salen de lo esperado, con reglas publicadas.

Uso interno. Una anomalía no es una alerta operativa ni una medición del riesgo: dice que
un conteo es difícil de explicar por azar frente a su propia historia reciente, para que
alguien lo mire. Las reglas se publican con el resultado (RULES) y no dependen de la IA.

Datos: hechos únicos de la sábana policial (un hecho por identidad, la entrega más
reciente gana), con la misma clasificación territorial del radar de la Defensoría.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.sat_radar_service import CONDUCTA_LABELS, _classifier, _events, load_registry

HIGH_P = 0.001
MEDIUM_P = 0.01
MIN_RATIO = 2.0  # además de improbable, al menos el doble de lo esperado

WEEK = 7
MUNICIPAL_BASELINE_WEEKS = 12
MUNICIPAL_MIN_OBSERVED = 3

TERRITORY_WINDOW = 28
TERRITORY_BASELINE_DAYS = 182
TERRITORY_MIN_OBSERVED = 4

SMOOTHING = 0.5  # medio hecho sumado a la historia: sin él, un lugar sin hechos previos daría "esperado 0"
DROP_MIN_EXPECTED = 10  # solo se buscan caídas donde lo normal son 10 o más hechos
TERRITORY_GROUPS = {"AT", "SECTOR_AT", "RURAL_NO_AT", "URBANO"}  # sin polígono oficial no se analiza

RULES = [
    {"code": "R1", "title": "Municipio, por conducta, cada semana",
     "text": "Los hechos de la última semana (7 días al corte) se comparan con el promedio semanal de las 12 semanas anteriores."},
    {"code": "R2", "title": "Barrio, vereda o sector, cada 28 días",
     "text": "Los hechos de los últimos 28 días se comparan con lo esperado según los 6 meses anteriores "
             "(26 semanas, llevado a 28 días). Por semana hay muy pocos hechos por barrio para concluir algo."},
    {"code": "R3", "title": "Caídas bruscas del total municipal",
     "text": "Una semana con muchos menos hechos de lo esperado (donde lo normal son 10 o más) se reporta como posible "
             "falta de registro, no como mejora. No se revisa la última semana: los registros tardíos aún la completan."},
    {"code": "PRUEBA", "title": "Cuándo hay señal estadística",
     "text": "Se calcula la probabilidad de ver esa cifra o una más extrema si nada hubiera cambiado (distribución de Poisson "
             "con la media esperada). Alta: menos de 0,1 %. Media: menos de 1 %. Además, un aumento debe ser al menos el doble "
             "de lo esperado y tener un mínimo de hechos (3 en el municipio, 4 en un territorio). A la historia se le suma "
             "medio hecho, para que un lugar sin hechos previos no parezca imposible con uno solo."},
    {"code": "LIMITES", "title": "Qué no dice",
     "text": "No mide riesgo ni causas, no reemplaza el análisis del Observatorio y no se publica. Con muchas pruebas, algunas "
             "señales serán azar: el radar informa cuántas se esperan. Solo cuenta hechos conocidos por la Policía."},
]


def poisson_upper(observed: int, expected: float) -> float:
    """P(X >= observed) con X ~ Poisson(expected)."""
    if observed <= 0:
        return 1.0
    if expected <= 0:
        return 0.0
    term = math.exp(-expected)
    cumulative = term
    for k in range(1, observed):
        term *= expected / k
        cumulative += term
    return max(0.0, 1.0 - cumulative)


def poisson_lower(observed: int, expected: float) -> float:
    """P(X <= observed) con X ~ Poisson(expected)."""
    if expected <= 0:
        return 1.0
    term = math.exp(-expected)
    cumulative = term
    for k in range(1, observed + 1):
        term *= expected / k
        cumulative += term
    return min(1.0, cumulative)


def level_for(p_value: float) -> Optional[str]:
    if p_value < HIGH_P:
        return "ALTA"
    if p_value < MEDIUM_P:
        return "MEDIA"
    return None


def test_increase(observed: int, expected: float, min_observed: int) -> Optional[Dict[str, Any]]:
    if observed < min_observed or observed < MIN_RATIO * expected:
        return None
    p_value = poisson_upper(observed, expected)
    level = level_for(p_value)
    if not level:
        return None
    return {"kind": "AUMENTO", "level": level, "observed": observed, "expected": round(expected, 1), "p_value": p_value,
            "ratio": round(observed / expected, 1) if expected else None}


def test_drop(observed: int, expected: float) -> Optional[Dict[str, Any]]:
    if expected < DROP_MIN_EXPECTED or observed > expected / MIN_RATIO:
        return None
    p_value = poisson_lower(observed, expected)
    level = level_for(p_value)
    if not level:
        return None
    return {"kind": "CAIDA", "level": level, "observed": observed, "expected": round(expected, 1), "p_value": p_value,
            "ratio": round(observed / expected, 2)}


def _probability_text(p_value: float) -> str:
    if p_value < 0.0001:
        return "menos de 1 en 10.000"
    return f"{p_value * 100:.2f}".replace(".", ",") + " %"


def _fmt(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _count(events, start: date, end: date, key=None) -> Counter:
    counter: Counter = Counter()
    for event in events:
        if start <= event["fecha"] <= end:
            counter[key(event) if key else "total"] += 1
    return counter


def build_anomalies(db: Session, cutoff: Optional[date] = None) -> Dict[str, Any]:
    rows = _events(db)
    if not rows:
        return {"status": "SIN_DATOS", "reason": "No hay hechos de la sábana policial cargados.", "anomalies": [], "rules": RULES}
    today = date.today()
    cutoff = cutoff or min(max(row.fecha for row in rows), today)
    classify, _ = _classifier(load_registry())
    events = []
    for row in rows:
        if row.fecha > cutoff:
            continue
        group, name = classify(row.lugar)
        events.append({"fecha": row.fecha, "conducta": row.conducta, "group": group, "territory": name})

    anomalies: List[Dict[str, Any]] = []
    tests = 0

    # R1: municipio por conducta, última semana frente a las 12 anteriores.
    week_start = cutoff - timedelta(days=WEEK - 1)
    base_start = week_start - timedelta(days=WEEK * MUNICIPAL_BASELINE_WEEKS)
    base_end = week_start - timedelta(days=1)
    current = _count(events, week_start, cutoff, key=lambda e: e["conducta"])
    baseline = _count(events, base_start, base_end, key=lambda e: e["conducta"])
    for conducta, label in CONDUCTA_LABELS.items():
        tests += 1
        expected = (baseline[conducta] + SMOOTHING) / MUNICIPAL_BASELINE_WEEKS
        result = test_increase(current[conducta], expected, MUNICIPAL_MIN_OBSERVED)
        if result:
            anomalies.append({**result, "rule": "R1", "scope": "MUNICIPIO", "conducta": label, "territory": "Jamundí",
                              "window": {"start": week_start.isoformat(), "end": cutoff.isoformat()},
                              "title": f"{label}: {result['observed']} hechos en la última semana",
                              "detail": f"Lo esperado según las 12 semanas anteriores era {_fmt(result['expected'])}. "
                                        f"Probabilidad de verlo por azar: {_probability_text(result['p_value'])}."})

    # R2: territorios, últimos 28 días frente a los 6 meses anteriores.
    window_start = cutoff - timedelta(days=TERRITORY_WINDOW - 1)
    tbase_start = window_start - timedelta(days=TERRITORY_BASELINE_DAYS)
    tbase_end = window_start - timedelta(days=1)
    located = [e for e in events if e["group"] in TERRITORY_GROUPS]
    current_t = _count(located, window_start, cutoff, key=lambda e: e["territory"])
    baseline_t = _count(located, tbase_start, tbase_end, key=lambda e: e["territory"])
    groups = {e["territory"]: e["group"] for e in located}
    conducts = defaultdict(Counter)
    for e in located:
        if window_start <= e["fecha"] <= cutoff:
            conducts[e["territory"]][e["conducta"]] += 1
    for territory in sorted(set(current_t) | set(baseline_t)):
        tests += 1
        expected = (baseline_t[territory] + SMOOTHING) * TERRITORY_WINDOW / TERRITORY_BASELINE_DAYS
        result = test_increase(current_t[territory], expected, TERRITORY_MIN_OBSERVED)
        if result:
            top = ", ".join(f"{CONDUCTA_LABELS.get(code, code.capitalize()).lower()} ({n})"
                            for code, n in conducts[territory].most_common(3))
            anomalies.append({**result, "rule": "R2", "scope": "TERRITORIO", "conducta": None, "territory": territory,
                              "territory_group": groups.get(territory),
                              "window": {"start": window_start.isoformat(), "end": cutoff.isoformat()},
                              "title": f"{territory}: {result['observed']} hechos en 28 días",
                              "detail": f"Lo esperado según los 6 meses anteriores era {_fmt(result['expected'])}. "
                                        f"Predomina: {top}. Probabilidad de verlo por azar: {_probability_text(result['p_value'])}."})

    # R3: caídas del total municipal en las semanas 2 a 4 antes del corte (la última aún se completa).
    for back in range(1, 4):
        end = cutoff - timedelta(days=WEEK * back)
        start = end - timedelta(days=WEEK - 1)
        tests += 1
        observed = _count(events, start, end)["total"]
        prior = _count(events, start - timedelta(days=WEEK * MUNICIPAL_BASELINE_WEEKS), start - timedelta(days=1))["total"]
        result = test_drop(observed, prior / MUNICIPAL_BASELINE_WEEKS)
        if result:
            anomalies.append({**result, "rule": "R3", "scope": "CALIDAD", "conducta": None, "territory": "Jamundí",
                              "window": {"start": start.isoformat(), "end": end.isoformat()},
                              "title": f"Semana del {start:%d/%m} al {end:%d/%m}: solo {observed} hechos registrados",
                              "detail": f"Lo esperado era {_fmt(result['expected'])}. Antes de leerlo como mejora, "
                                        "verifique que la entrega de la Policía esté completa."})

    order = {"ALTA": 0, "MEDIA": 1}
    anomalies.sort(key=lambda item: (order[item["level"]], item["p_value"]))
    return {
        "status": "OK",
        "cutoff": cutoff.isoformat(),
        "anomalies": anomalies,
        "tests": tests,
        # Si nada hubiera cambiado, cada prueba tiene hasta 1 % de dar una anomalía media por azar.
        "expected_false_alarms": round(tests * MEDIUM_P, 1),
        "rules": RULES,
        "note": "Uso interno. Una señal estadística pide mirar el dato; no es una alerta ni mide el riesgo. Solo la Defensoría del Pueblo emite Alertas Tempranas.",
    }
