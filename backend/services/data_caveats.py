"""Salvedades del dato para un periodo: cuándo una cifra de la sábana puede estar incompleta.

Las usa el Inicio para que una baja que puede ser falta de registro no se lea como mejora.
Son las mismas reglas del Centro de análisis:
- los últimos 7 días de una entrega policial suelen completarse con reportes tardíos;
- el radar marca las semanas con muchos menos hechos de lo esperado (regla R3);
- una sábana con más de 10 días ya no describe el presente;
- los días posteriores al corte no tienen datos.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

PRELIMINARY_LAG_DAYS = 7  # igual que SiscCifrasService.PRELIMINARY_LAG_DAYS
STALE_DAYS = 10


def _d(day: date) -> str:
    return f"{day.day:02d}/{day.month:02d}"


def build_caveats(db: Session, start: date, end: date, today: Optional[date] = None) -> Dict[str, Any]:
    from services.anomaly_radar import build_anomalies
    from services.intervention_followup import latest_covering_run

    today = today or date.today()
    run = latest_covering_run(db)
    items: List[str] = []
    if run is None:
        return {"incomplete": True, "items": ["No hay una entrega completa de la sábana policial: las cifras no se pueden comparar."]}
    cutoff = run.cobertura_fin
    if end > cutoff:
        items.append(f"El periodo termina después del corte de la sábana ({_d(cutoff)}): los días siguientes todavía no tienen datos.")
    tail_start = cutoff - timedelta(days=PRELIMINARY_LAG_DAYS - 1)
    if start <= cutoff and end >= tail_start:
        items.append(f"Incluye los últimos {PRELIMINARY_LAG_DAYS} días de la entrega (hasta el {_d(cutoff)}), que suelen "
                     "completarse con reportes tardíos.")
    radar = build_anomalies(db)
    for anomaly in radar.get("anomalies", []) if radar.get("status") == "OK" else []:
        window = anomaly.get("window") or {}
        if anomaly.get("rule") != "R3" or not window:
            continue
        w_start, w_end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        if w_start <= end and w_end >= start:
            items.append(f"{anomaly['title']}. {anomaly['detail']}")
    age = (today - cutoff).days
    if age > STALE_DAYS:
        items.append(f"La sábana llega hasta el {_d(cutoff)} ({age} días): no describe lo ocurrido después.")
    return {
        "incomplete": bool(items),
        "cutoff": cutoff.isoformat(),
        "items": items,
        "reading": ("Una baja frente al periodo de comparación puede ser falta de registro, no una mejora. "
                    "Confírmela cuando llegue la siguiente entrega.") if items else "",
    }
