"""Seguimiento de una intervención a 30, 60 y 90 días de su inicio.

Cada ventana compara los N días desde el inicio con los N días anteriores, en el mismo
indicador municipal y sobre la misma entrega policial (reproducible). Es descriptivo:
no demuestra que la intervención haya causado el cambio.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from db.models_hechos_seguridad import IngestionRun
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import FOLLOWUP_INDICATORS, METHODOLOGY_VERSION, get_indicator_meta

WINDOWS = (30, 60, 90)
SMALL_BASE = 30  # con menos de 30 hechos antes, se informa la diferencia en casos, no el porcentaje
NOTE = "Cambio observado entre periodos; no demuestra que la intervención lo haya causado."


def case_indicator(document: Dict[str, Any]) -> Optional[str]:
    """Indicador elegido en el expediente o, si nació de una alerta municipal, el de la alerta."""
    if document.get("indicator"):
        return document["indicator"]
    entity = (document.get("alert_snapshot") or {}).get("entity_ref") or {}
    if entity.get("indicator") in FOLLOWUP_INDICATORS and entity.get("territory") == "JAMUNDI":
        return entity["indicator"]
    return None


def latest_covering_run(db) -> Optional[IngestionRun]:
    return (
        db.query(IngestionRun)
        .filter(IngestionRun.fuente_codigo == "POLICIA_SEMANAL", IngestionRun.status == "COMPLETED",
                IngestionRun.cobertura_inicio.isnot(None), IngestionRun.cobertura_fin.isnot(None))
        .order_by(IngestionRun.cobertura_fin.desc(), IngestionRun.fecha_inicio.desc().nullslast())
        .first()
    )


def window_plan(started_on: date, days: int) -> Dict[str, date]:
    return {
        "before_start": started_on - timedelta(days=days),
        "before_end": started_on - timedelta(days=1),
        "after_start": started_on,
        "after_end": started_on + timedelta(days=days - 1),
    }


def describe_change(before: int, after: int) -> Dict[str, Any]:
    difference = after - before
    small = before < SMALL_BASE
    return {
        "before": before,
        "after": after,
        "difference": difference,
        "variation_pct": None if small or not before else round(difference / before * 100, 1),
        "small_base": small,
    }


def followup(db, document: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    indicator = case_indicator(document)
    if not indicator:
        return {"status": "SIN_INDICADOR", "windows": [], "note": NOTE,
                "reason": "Elija qué indicador debería cambiar con esta intervención."}
    if not document.get("started_on"):
        return {"status": "SIN_INICIO", "indicator": indicator, "windows": [], "note": NOTE,
                "reason": "El seguimiento empieza cuando se registra la fecha de inicio de la intervención."}
    started_on = date.fromisoformat(document["started_on"])
    run = latest_covering_run(db)
    if not run:
        return {"status": "SIN_DATOS", "indicator": indicator, "windows": [], "note": NOTE,
                "reason": "No hay una entrega policial completa con cobertura declarada."}

    meta = get_indicator_meta(indicator)
    windows = []
    for days in WINDOWS:
        plan = window_plan(started_on, days)
        row = {"days": days, **{key: value.isoformat() for key, value in plan.items()}}
        if plan["after_end"] >= today:
            row.update(status="PENDIENTE", detail=f"Se podrá medir desde el {plan['after_end'] + timedelta(days=1):%d/%m/%Y}.")
        elif plan["after_end"] > run.cobertura_fin:
            row.update(status="ESPERANDO_DATOS",
                       detail=f"La sábana policial llega hasta el {run.cobertura_fin:%d/%m/%Y}; falta cargar semanas.")
        elif plan["before_start"] < run.cobertura_inicio:
            row.update(status="SIN_BASE",
                       detail=f"La entrega empieza el {run.cobertura_inicio:%d/%m/%Y}: no cubre el periodo anterior.")
        else:
            kwargs = dict(indicator=indicator, territory="JAMUNDI", source_version_id=str(run.id),
                          methodology_version=METHODOLOGY_VERSION)
            before = calculate_indicator(db, period_start=plan["before_start"], period_end=plan["before_end"], **kwargs)
            after = calculate_indicator(db, period_start=plan["after_start"], period_end=plan["after_end"], **kwargs)
            row.update(status="MEDIDO", **describe_change(int(before["value"]), int(after["value"])))
        windows.append(row)
    return {
        "status": "OK",
        "indicator": indicator,
        "indicator_label": meta.get("label", indicator),
        "unit_label": meta["unit_label"],
        "territory": "Jamundí (municipio)",
        "started_on": started_on.isoformat(),
        "source_version_id": str(run.id),
        "coverage": {"start": run.cobertura_inicio.isoformat(), "end": run.cobertura_fin.isoformat()},
        "windows": windows,
        "note": NOTE,
    }
