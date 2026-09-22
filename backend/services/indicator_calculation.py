"""Única función de cálculo backend — fuente de verdad para tablero, boletín, alertas y chat.

Contrato de entrada:
{
  "indicator": "HOMICIDIO",
  "period": {"start": "2026-01-01", "end": "2026-07-12"},
  "territory": "JAMUNDI",
  "source_version_id": "...",   # UUID IngestionRun o null = vigente consolidado
  "methodology_version": "1"
}

Contrato de salida:
{
  "value": 54,
  "unit": "hechos registrados",
  "source_version_id": "...",
  "methodology_version": "1",
  "query_hash": "...",
  "quality_status": "VALIDATED"
}

Reglas:
- source_version_id identifica inequívocamente la entrega (IngestionRun.id).
- methodology_version cambia cuando cambie una regla de conteo.
- El frontend envía filtros y muestra resultados; no recalcula sobre el Excel
  para cifras oficiales.
- HOMICIDIO usa hechos únicos (igual que el resto), no COUNT de filas.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from services.hechos_metrics import hechos_unicos_expr, persona_identificable_filter
from services.indicator_catalog import METHODOLOGY_VERSION, get_indicator_meta


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _resolve_source_version(db: Session, source_version_id: Optional[str]) -> Optional[IngestionRun]:
    if not source_version_id:
        return None
    try:
        run_uuid = UUID(str(source_version_id))
    except ValueError:
        raise ValueError(f"source_version_id inválido: {source_version_id}")
    run = db.query(IngestionRun).filter(
        IngestionRun.id == run_uuid,
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
    ).first()
    if not run:
        raise ValueError(f"No existe la entrega policial {source_version_id}")
    return run


def _latest_completed_run(db: Session) -> Optional[IngestionRun]:
    return (
        db.query(IngestionRun)
        .filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.status == "COMPLETED",
        )
        .order_by(IngestionRun.fecha_fin.desc().nullslast(), IngestionRun.fecha_inicio.desc().nullslast())
        .first()
    )


def _quality_status(value: int, cutoff: Optional[date]) -> str:
    if value <= 0 or not cutoff:
        return "PRELIMINARY"
    return "VALIDATED"


def calculate_indicator(
    db: Session,
    *,
    indicator: str,
    period_start: Any,
    period_end: Any,
    territory: str = "JAMUNDI",
    source_version_id: Optional[str] = None,
    methodology_version: str = METHODOLOGY_VERSION,
) -> Dict[str, Any]:
    """Calcula un indicador con reglas centralizadas. Única vía oficial.

    - `source_version_id=None` = exploración sobre consolidado vigente (NO publicable).
      Para publicar hay que fijar la entrega (IngestionRun.id).
    - Solo la metodología vigente es ejecutable. Pedir una antigua devuelve
      error explícito; guardar "methodology_version" no garantiza reproducibilidad
      si la regla ya no existe en código.
    """
    SUPPORTED = {METHODOLOGY_VERSION}
    if methodology_version not in SUPPORTED:
        raise ValueError(
            f"methodology_version={methodology_version} no ejecutable. "
            f"Soportadas: {sorted(SUPPORTED)}. Si necesita reproducir historia con "
            "regla antigua, restaure el código de esa versión; no se recalcula con la regla nueva."
        )
    meta = get_indicator_meta(indicator)
    start = _parse_date(period_start)
    end = _parse_date(period_end)
    if start > end:
        raise ValueError("period.start debe ser anterior a period.end")
    if (territory or "JAMUNDI").strip().upper() != "JAMUNDI":
        raise ValueError("Solo se soporta territory=JAMUNDI en metodología v1.")

    run = _resolve_source_version(db, source_version_id)
    effective_source_id = str(run.id) if run else None
    if run is None:
        latest = _latest_completed_run(db)
        effective_source_id = str(latest.id) if latest else None

    # Base: hechos únicos por defecto; registros solo para diagnóstico.
    if indicator == "POLICIA_REGISTROS":
        if run is not None:
            value = (
                db.query(func.count(SabanaSnapshotRow.id))
                .filter(
                    SabanaSnapshotRow.ingestion_id == run.id,
                    SabanaSnapshotRow.fecha_evento >= start,
                    SabanaSnapshotRow.fecha_evento <= end,
                )
                .scalar()
                or 0
            )
        else:
            value = (
                db.query(func.count(HechoSeguridad.id))
                .filter(
                    HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
                    HechoSeguridad.fecha_evento >= start,
                    HechoSeguridad.fecha_evento <= end,
                )
                .scalar()
                or 0
            )
    elif indicator == "HOMICIDIO_VICTIMAS":
        # Víctimas: filas identificables en el periodo (unidad VICTIMA).
        base = [
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= end,
            HechoSeguridad.conducta_estandar.in_(meta["conducta_filter"]),
            persona_identificable_filter(),
        ]
        if run is not None:
            base.append(HechoSeguridad.ingestion_id == run.id)
        value = db.query(func.count(HechoSeguridad.id)).filter(*base).scalar() or 0
    else:
        # HOMICIDIO y SEGURIDAD_TOTAL: COUNT DISTINCT hecho_key (unidad HECHO).
        base = [
            HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
            HechoSeguridad.fecha_evento >= start,
            HechoSeguridad.fecha_evento <= end,
        ]
        if meta.get("conducta_filter"):
            base.append(HechoSeguridad.conducta_estandar.in_(meta["conducta_filter"]))
        if run is not None:
            # Reproducibilidad histórica: calcula sobre la foto de la entrega.
            value = (
                db.query(func.count(func.distinct(SabanaSnapshotRow.hecho_key)))
                .filter(
                    SabanaSnapshotRow.ingestion_id == run.id,
                    SabanaSnapshotRow.fecha_evento >= start,
                    SabanaSnapshotRow.fecha_evento <= end,
                    *(
                        [SabanaSnapshotRow.conducta_estandar.in_(meta["conducta_filter"])]
                        if meta.get("conducta_filter")
                        else []
                    ),
                )
                .scalar()
                or 0
            )
        else:
            value = db.query(hechos_unicos_expr()).filter(*base).scalar() or 0

    cutoff = (
        db.query(func.max(HechoSeguridad.fecha_evento))
        .filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL")
        .scalar()
    )
    quality = _quality_status(int(value), cutoff)

    query_payload = {
        "indicator": indicator,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "territory": "JAMUNDI",
        "source_version_id": effective_source_id,
        "methodology_version": methodology_version,
    }
    query_hash = hashlib.sha256(
        json.dumps(query_payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    return {
        "value": int(value),
        "unit": meta["unit_label"],
        "unit_code": meta["unit"],
        "indicator": indicator,
        "source_version_id": effective_source_id,
        "methodology_version": methodology_version,
        "query_hash": query_hash,
        "quality_status": quality,
        "reproducible": run is not None,
        "exploratory": run is None,
        "publication_note": (
            "Exploración sobre consolidado vigente; fije source_version_id para publicar."
            if run is None
            else "Cálculo reproducible sobre entrega fijada."
        ),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "territory": "JAMUNDI",
    }
