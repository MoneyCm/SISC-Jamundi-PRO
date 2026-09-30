"""Metas de resultado del PISCC 2024-2027 (tabla 16) frente a lo que lleva el año.

Cada indicador se mide con su propia fuente y su propio corte; los cortes no se mezclan.
- Homicidios, hurto a motocicletas y lesiones: MinDefensa (datos.gov.co) hasta el último mes
  publicado, porque la línea base 2023 y la meta están en esa fuente y cuentan víctimas. La
  sábana policial (hechos únicos) cuenta un hecho con dos víctimas como uno: con ella el avance
  quedaba por debajo (lesiones, un 10 % menos). La cifra de la sábana se conserva como dato
  reciente ("reciente"), sin sumarla. Si MinDefensa no tiene meses del año, se usa la sábana.
- Secuestro, extorsión y violencia intrafamiliar: MinDefensa; convivencia: RNMC.

La meta es la cifra anual a la que el plan quiere llegar en 2027. Se compara con el año en
curso de dos formas, según el tamaño de la meta:
- Meta de 20 o más: proyección lineal al cierre del año (acumulado / días transcurridos x días del año).
- Meta menor de 20: con tan pocos casos la proyección no dice nada; se compara el acumulado.
Antes de 8 semanas el resultado es preliminar y no se señala desviación.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SOURCE = "PISCC 2024-2027, tabla 16 (indicadores de resultado)"
# id, indicador, línea base 2023, meta 2027, indicador del SISC (None = fuente externa)
TABLE_16 = (
    ("homicidios", "Homicidios", 115, 105, "HOMICIDIO"),
    ("secuestro", "Secuestro", 4, 3, None),
    ("extorsion", "Extorsión", 58, 55, None),
    ("vif", "Violencia intrafamiliar", 187, 180, None),
    ("motos", "Hurto a motocicletas", 200, 180, "HURTO_MOTOS"),
    ("lesiones", "Lesiones personales", 453, 430, "LESIONES"),
    ("convivencia", "Comportamientos contrarios a la convivencia", 4798, 4000, None),
)
GOALS = {key: goal for key, _label, _base, goal, _indicator in TABLE_16}
SMALL_GOAL = 20
MIN_DAYS = 56  # 8 semanas
STALE_DAYS = 45  # un corte más viejo que esto se advierte al lado de la cifra

STATUS_LABELS = {
    "EN_META": "En la meta",
    "DESVIACION": "Desviación",
    "SUPERADA": "Meta superada en el año",
    "PRELIMINAR": "Preliminar",
    "SIN_DATOS": "Sin datos",
}


def _days_in_year(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


def evaluate(count: int, cutoff: date, goal: int) -> Dict[str, Any]:
    """Estado de un indicador con `count` hechos del 1 de enero al `cutoff`, frente a la meta anual."""
    elapsed = (cutoff - date(cutoff.year, 1, 1)).days + 1
    projection = round(count * _days_in_year(cutoff.year) / elapsed)
    small = goal < SMALL_GOAL
    result = {"count": count, "cutoff": cutoff.isoformat(), "days_elapsed": elapsed,
              "projection": None if small else projection, "compares": "acumulado" if small else "proyeccion"}
    if count > goal:
        status = "SUPERADA"
        detail = f"En lo corrido del año van {count}, más que la meta anual de {goal}."
    elif elapsed < MIN_DAYS:
        status = "PRELIMINAR"
        detail = f"Van {count} en {elapsed} días: muy pronto para proyectar el año."
    elif small:
        status = "EN_META"
        detail = f"Van {count} en lo corrido del año; la meta anual es {goal}. Base pequeña: se compara el acumulado, no una proyección."
    elif projection > goal:
        status = "DESVIACION"
        detail = f"Van {count}; a este ritmo el año cerraría cerca de {projection}, por encima de la meta de {goal}."
    else:
        status = "EN_META"
        detail = f"Van {count}; a este ritmo el año cerraría cerca de {projection}, dentro de la meta de {goal}."
    return {**result, "status": status, "detail": detail}


def _police_rows(db: Session, today: date, source_version_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    from db.models_hechos_seguridad import IngestionRun
    from services.indicator_calculation import calculate_indicator
    from services.indicator_catalog import METHODOLOGY_VERSION
    from services.intervention_followup import latest_covering_run

    # El boletín fija su entrega; el Centro de análisis usa la última completa.
    run = db.get(IngestionRun, UUID(source_version_id)) if source_version_id else latest_covering_run(db)
    if run is not None and run.fuente_codigo != "POLICIA_SEMANAL":
        run = None
    police = [(key, indicator) for key, _l, _b, _g, indicator in TABLE_16 if indicator]
    if not run or not run.cobertura_inicio or not run.cobertura_fin:
        return {key: {"status": "SIN_DATOS", "detail": "No hay una entrega policial completa con cobertura declarada."}
                for key, _ in police}
    cutoff = min(today, run.cobertura_fin)
    start = date(cutoff.year, 1, 1)
    if run.cobertura_inicio > start:
        reason = f"La entrega policial empieza el {run.cobertura_inicio:%d/%m/%Y}: no cubre el año desde el 1 de enero."
        return {key: {"status": "SIN_DATOS", "detail": reason} for key, _ in police}

    previous_start = date(cutoff.year - 1, 1, 1)
    has_previous = run.cobertura_inicio <= previous_start
    kwargs = dict(territory="JAMUNDI", source_version_id=str(run.id), methodology_version=METHODOLOGY_VERSION)
    rows = {}
    for key, indicator in police:
        count = int(calculate_indicator(db, indicator=indicator, period_start=start, period_end=cutoff, **kwargs)["value"])
        previous = None
        if has_previous:
            # Mismo tramo del año anterior (el 29 de febrero cae en el 28).
            leap_day = (cutoff.month, cutoff.day) == (2, 29)
            previous_end = cutoff.replace(year=cutoff.year - 1, day=28 if leap_day else cutoff.day)
            previous = int(calculate_indicator(db, indicator=indicator, period_start=previous_start,
                                               period_end=previous_end, **kwargs)["value"])
        rows[key] = {**evaluate(count, cutoff, GOALS[key]), "previous": previous,
                     "source": "Sábana policial (hechos únicos)", "source_version_id": str(run.id)}
    return rows


MINDEFENSA_MENSUAL = ("homicidios", "motos", "lesiones")
FUENTE_MINDEFENSA = "MinDefensa / Policía Nacional (víctimas, datos.gov.co)"


def _mindefensa_rows(db: Session, today: date, datos: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Año corrido con MinDefensa: meses cerrados publicados hasta `today` (misma fuente y unidad de la meta)."""
    from calendar import monthrange

    from services import piscc_historico

    datos = datos if datos is not None else piscc_historico.cargar()
    publicado = piscc_historico._ultimo_publicado(datos)
    if not publicado:
        return {}
    ultimo_cerrado = (today.year, today.month) if today.day == monthrange(today.year, today.month)[1] else (
        (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
    anio, mes = min(publicado, ultimo_cerrado)
    if anio != today.year:
        return {}  # sin meses publicados del año en curso
    cutoff = date(anio, mes, monthrange(anio, mes)[1])
    rows = {}
    for key in MINDEFENSA_MENSUAL:
        actual = piscc_historico.serie_mensual(key, anio, datos)[:mes]
        previo = piscc_historico.serie_mensual(key, anio - 1, datos)[:mes]
        count = sum(v or 0 for v in actual)
        previous = sum(previo) if previo and all(v is not None for v in previo) else None
        rows[key] = {**evaluate(count, cutoff, GOALS[key]), "previous": previous, "source": FUENTE_MINDEFENSA}
    return rows


def _external_rows(db: Session, today: date) -> Dict[str, Dict[str, Any]]:
    from services.piscc_sources_service import load_mindefensa, load_rnmc

    rows: Dict[str, Dict[str, Any]] = {}
    items, _notices = load_mindefensa(today)
    try:
        rnmc = load_rnmc(db, today)
    except Exception:
        logger.exception("Metas PISCC: no se pudo consultar RNMC")
        rnmc = None
    if rnmc:
        items["convivencia"] = rnmc
    for key, item in items.items():
        cutoff = date.fromisoformat(item["fechaCorte"])
        rows[key] = {**evaluate(int(item["countBase"]), cutoff, GOALS[key]),
                     "previous": item.get("countPrev"), "source": item["fuenteNombre"]}
    return rows


def short_text(item: Dict[str, Any]) -> str:
    if item["compares"] == "acumulado" or item["status"] == "SUPERADA":
        return f"{item['label']}: {item['count']} en el año (meta {item['goal_2027']})"
    return f"{item['label']}: ritmo de ≈{item['projection']} (meta {item['goal_2027']})"


def _convivencia_anios(db: Session, baseline: int, goal: int, today: date) -> List[Dict[str, Any]]:
    """Comparendos únicos del RNMC por año cerrado; sin enero a diciembre completos no se califica."""
    from services import comparendos_rnmc, piscc_historico

    anios = []
    for anio in range(2024, today.year):
        desde, hasta = date(anio, 1, 1), date(anio, 12, 31)
        try:
            total = comparendos_rnmc.contar(db, desde, hasta)
            completo = comparendos_rnmc.cubre(db, desde, hasta)
        except Exception:
            db.rollback()
            total, completo = 0, False
        estado = piscc_historico.semaforo(total, baseline, goal) if completo else None
        etiqueta = piscc_historico.SEMAFORO.get(estado) if estado else (
            "Reportes del RNMC incompletos para ese año" if total else "Sin reportes del RNMC de ese año")
        anios.append({"anio": anio, "total": total or None, "completo": completo, "semaforo": estado, "semaforo_label": etiqueta})
    return anios


def build_goals(db: Session, today: Optional[date] = None, source_version_id: Optional[str] = None) -> Dict[str, Any]:
    """`today` es la fecha de corte: la del día en el Centro de análisis, el fin del periodo en el boletín."""
    today = today or date.today()
    measured: Dict[str, Dict[str, Any]] = {}
    for loader, label, args in ((_police_rows, "sábana policial", (source_version_id,)), (_external_rows, "fuentes externas", ())):
        try:
            measured.update(loader(db, today, *args))
        except Exception:
            logger.exception("Metas PISCC: no se pudo leer %s", label)
    indicators: List[Dict[str, Any]] = []
    from services import piscc_historico

    historico = piscc_historico.cargar()
    try:
        mindefensa = _mindefensa_rows(db, today, historico)
    except Exception:
        logger.exception("Metas PISCC: no se pudo leer la serie mensual de MinDefensa")
        mindefensa = {}
    for key, row in mindefensa.items():
        sabana = measured.get(key) or {}
        reciente = ({"count": sabana["count"], "cutoff": sabana["cutoff"], "source": sabana.get("source")}
                    if sabana.get("count") is not None and sabana.get("cutoff", "") > row["cutoff"] else None)
        measured[key] = {**row, "reciente": reciente}
    for key, label, baseline, goal, _indicator in TABLE_16:
        row = measured.get(key) or {"status": "SIN_DATOS", "detail": "La fuente de este indicador no tiene un corte disponible."}
        if row.get("cutoff"):
            lag = (today - date.fromisoformat(row["cutoff"])).days
            row = {**row, "stale": lag > STALE_DAYS, "lag_days": lag}
        if key == "convivencia":
            anios = _convivencia_anios(db, baseline, goal, today)
        else:
            anios = piscc_historico.anios_cerrados(key, baseline, goal, today, historico)
        indicators.append({"id": key, "label": label, "baseline_2023": baseline, "goal_2027": goal,
                           "status_label": STATUS_LABELS[row["status"]], "closed_years": anios, **row})
    return {
        "as_of": today.isoformat(),
        "source": SOURCE,
        "indicators": indicators,
        "off_track": [item["id"] for item in indicators if item["status"] in ("DESVIACION", "SUPERADA")],
        "note": ("Cada indicador tiene su fuente y su fecha de corte. La meta es la cifra anual esperada en 2027; "
                 "la proyección es lineal y solo indica el ritmo, no predice el cierre."),
        "closed_years_source": piscc_historico.FUENTE,
        "closed_years_legend": piscc_historico.SEMAFORO,
    }
