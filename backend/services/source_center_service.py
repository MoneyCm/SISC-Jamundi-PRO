from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import HechoSeguridad, IngestionRun
from db.models_intelligence import NationalCrimeStats
from db.models_source_center import SourceConnectorState
from services.hechos_metrics import hechos_unicos_expr


SOURCE_CONNECTORS: Dict[str, Dict[str, Any]] = {
    "POLICIA_JAMUNDI": {
        "name": "Policia Jamundi",
        "institution": "Estacion de Policia Jamundi",
        "scope": "Municipal",
        "purpose": "Fuente operativa principal",
        "update_mode": "MANUAL",
        "expected_frequency": "Semanal",
        "source_url": None,
        "action_type": "UPLOAD",
        "action_label": "Cargar sabana semanal",
        "dataset_code": "POLICIA_SEMANAL",
        "fresh_days": 14,
        "lagged_days": 35,
    },
    "POLICIA_NACIONAL": {
        "name": "Policia Nacional",
        "institution": "Policia Nacional de Colombia",
        "scope": "Registros oficiales nacionales filtrados para Jamundi",
        "purpose": "Contraste mensual oficial de la sabana semanal",
        "update_mode": "AUTOMATIC_EXTERNAL",
        "expected_frequency": "Revision diaria; publicacion mensual",
        "source_url": "https://chat.policia.gov.co/estadistica-delictiva",
        "action_type": "OPEN",
        "action_label": "Abrir fuente oficial",
        "dataset_code": None,
        "fresh_days": 55,
        "lagged_days": 90,
    },
    "MINDEFENSA": {
        "name": "Ministerio de Defensa",
        "institution": "Ministerio de Defensa Nacional",
        "scope": "Series nacionales historicas filtradas para Jamundi",
        "purpose": "Respaldo historico de Policia Nacional",
        "update_mode": "AUTOMATIC_EXTERNAL",
        "expected_frequency": "Revision diaria segun cambios",
        "source_url": "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica",
        "action_type": "OPEN",
        "action_label": "Abrir fuente oficial",
        "dataset_code": None,
        "fresh_days": 55,
        "lagged_days": 90,
    },
    "SIEDCO_PUBLICO": {
        "name": "SIEDCO publico",
        "institution": "Policia Nacional de Colombia",
        "scope": "Portal publico filtrado para Jamundi",
        "purpose": "Validacion mensual del contraste oficial",
        "update_mode": "AUTOMATIC_EXTERNAL",
        "expected_frequency": "Mensual y bajo demanda",
        "source_url": "https://portalsiedco.policia.gov.co:4443/extensions/PortalPublico/index.html#/home",
        "action_type": "OPEN",
        "action_label": "Abrir fuente",
        "dataset_code": None,
        "fresh_days": 55,
        "lagged_days": 90,
    },
    "OBSERVATORIO_VALLE": {
        "name": "Observatorio del Valle",
        "institution": "Observatorio del Delito del Valle",
        "scope": "Contexto territorial de Jamundi",
        "purpose": "Analisis regional para el cierre mensual",
        "update_mode": "AUTOMATIC_EXTERNAL",
        "expected_frequency": "Semanal",
        "source_url": "https://www.observatoriodeldelitovalle.co/",
        "action_type": "OPEN",
        "action_label": "Abrir fuente",
        "dataset_code": None,
        "fresh_days": 10,
        "lagged_days": 24,
    },
}

STATUS_LABELS = {
    "CURRENT": "Al dia",
    "LAGGED": "Con rezago",
    "EXPIRED": "Desactualizada",
    "UPDATE_AVAILABLE": "Nueva version",
    "ERROR": "Requiere atencion",
    "NOT_CONNECTED": "Sin conexion",
    "NEEDS_REVIEW": "Sin revisar",
}

QUALITY_LABELS = {
    "VALIDATED": "Validada",
    "WARNING": "Con advertencias",
    "INCOMPLETE": "Incompleta",
    "ERROR": "Con error",
}


def _as_iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def freshness_status(cutoff: Optional[date], fresh_days: int, lagged_days: int) -> str:
    if cutoff is None:
        return "NO_CUTOFF"
    age = max((date.today() - cutoff).days, 0)
    if age <= fresh_days:
        return "CURRENT"
    if age <= lagged_days:
        return "LAGGED"
    return "EXPIRED"


def overall_status(
    *,
    connected: bool,
    monitor_status: Optional[str],
    freshness: str,
    last_checked_at: Optional[datetime],
) -> str:
    normalized = (monitor_status or "").upper()
    if normalized == "ERROR":
        return "ERROR"
    if not connected:
        return "NOT_CONNECTED"
    if normalized in {"UPDATED", "UPDATE_AVAILABLE"}:
        return "UPDATE_AVAILABLE"
    if last_checked_at is None:
        return "NEEDS_REVIEW"
    if freshness == "NO_CUTOFF":
        return "NEEDS_REVIEW"
    if freshness in {"LAGGED", "EXPIRED"}:
        return freshness
    return "CURRENT"


class SourceCenterService:
    @staticmethod
    def _state_map(db: Session) -> Dict[str, SourceConnectorState]:
        try:
            return {row.connector_code: row for row in db.query(SourceConnectorState).all()}
        except SQLAlchemyError:
            db.rollback()
            return {}

    @staticmethod
    def _base(code: str) -> Dict[str, Any]:
        config = SOURCE_CONNECTORS[code]
        return {
            "code": code,
            "name": config["name"],
            "institution": config["institution"],
            "scope": config["scope"],
            "purpose": config["purpose"],
            "update_mode": config["update_mode"],
            "expected_frequency": config["expected_frequency"],
            "source_url": config["source_url"],
            "status": "NOT_CONNECTED",
            "status_label": STATUS_LABELS["NOT_CONNECTED"],
            "quality_status": "INCOMPLETE",
            "quality_label": QUALITY_LABELS["INCOMPLETE"],
            "freshness_status": "NO_CUTOFF",
            "source_cutoff_date": None,
            "last_checked_at": None,
            "last_success_at": None,
            "last_change_detected_at": None,
            "record_count": 0,
            "indicator_count": 0,
            "asset_count": 0,
            "updated_assets": 0,
            "error_assets": 0,
            "period_label": None,
            "warnings": [],
            "assets": [],
            "action": {
                "type": config["action_type"],
                "label": config["action_label"],
                "dataset_code": config["dataset_code"],
                "enabled": True,
            },
        }

    @staticmethod
    def _apply_state(connector: Dict[str, Any], state: Optional[SourceConnectorState]) -> Dict[str, Any]:
        if state is None:
            return connector
        connector.update(
            {
                "quality_status": state.quality_status or connector["quality_status"],
                "source_cutoff_date": _as_iso(state.source_cutoff_date),
                "last_checked_at": _as_iso(state.last_checked_at),
                "last_success_at": _as_iso(state.last_success_at),
                "last_change_detected_at": _as_iso(state.last_change_detected_at),
                "record_count": state.record_count or 0,
                "indicator_count": state.indicator_count or 0,
                "period_label": state.period_label,
                "warnings": list(state.warnings or []),
            }
        )
        config = SOURCE_CONNECTORS[connector["code"]]
        freshness = freshness_status(
            state.source_cutoff_date,
            config["fresh_days"],
            config["lagged_days"],
        )
        status = overall_status(
            connected=True,
            monitor_status=state.status,
            freshness=freshness,
            last_checked_at=state.last_checked_at,
        )
        connector.update(
            {
                "status": status,
                "status_label": STATUS_LABELS[status],
                "quality_label": QUALITY_LABELS.get(connector["quality_status"], "Por revisar"),
                "freshness_status": freshness,
            }
        )
        return connector

    @classmethod
    def _local_police(cls, db: Session, state: Optional[SourceConnectorState]) -> Dict[str, Any]:
        connector = cls._apply_state(cls._base("POLICIA_JAMUNDI"), state)
        facts, cutoff, last_ingestion = db.query(
            hechos_unicos_expr(HechoSeguridad),
            func.max(HechoSeguridad.fecha_evento),
            func.max(HechoSeguridad.fecha_ingesta),
        ).filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL").one()
        last_run = db.query(func.max(IngestionRun.fecha_fin)).filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.status == "COMPLETED",
        ).scalar()
        last_checked = last_run or last_ingestion
        config = SOURCE_CONNECTORS["POLICIA_JAMUNDI"]
        freshness = freshness_status(cutoff, config["fresh_days"], config["lagged_days"])
        status = overall_status(
            connected=bool(facts and cutoff),
            monitor_status="CURRENT",
            freshness=freshness,
            last_checked_at=last_checked,
        )
        connector.update(
            {
                "status": status,
                "status_label": STATUS_LABELS[status],
                "quality_status": "VALIDATED" if facts and cutoff else "INCOMPLETE",
                "quality_label": QUALITY_LABELS["VALIDATED" if facts and cutoff else "INCOMPLETE"],
                "freshness_status": freshness,
                "source_cutoff_date": _as_iso(cutoff),
                "last_checked_at": _as_iso(last_checked),
                "last_success_at": _as_iso(last_checked),
                "record_count": int(facts or 0),
                "period_label": f"Hasta {cutoff.isoformat()}" if cutoff else None,
            }
        )
        return connector

    @classmethod
    def _asset_connector(
        cls,
        db: Session,
        code: str,
        model: Any,
        state: Optional[SourceConnectorState],
    ) -> Dict[str, Any]:
        connector = cls._apply_state(cls._base(code), state)
        assets = db.query(model).order_by(model.display_name.asc()).all()
        asset_codes = [asset.dataset_code for asset in assets]
        cutoff = None
        record_count = 0
        if asset_codes:
            cutoff, record_count = db.query(
                func.max(NationalCrimeStats.fecha_hecho),
                func.count(NationalCrimeStats.id),
            ).filter(NationalCrimeStats.source_id.in_(asset_codes)).one()

        last_checked = max((_as_utc(asset.last_checked_at) for asset in assets if asset.last_checked_at), default=None)
        last_change = max(
            (_as_utc(asset.last_change_detected_at) for asset in assets if asset.last_change_detected_at),
            default=None,
        )
        updated = sum(1 for asset in assets if asset.status == "UPDATED")
        errors = sum(1 for asset in assets if asset.status == "ERROR")
        monitor_status = "ERROR" if errors else "UPDATED" if updated else "CURRENT"
        config = SOURCE_CONNECTORS[code]
        effective_cutoff = cutoff or (state.source_cutoff_date if state else None)
        effective_checked = last_checked or (_as_utc(state.last_checked_at) if state else None)
        freshness = freshness_status(effective_cutoff, config["fresh_days"], config["lagged_days"])
        status = overall_status(
            connected=bool(assets or state),
            monitor_status=monitor_status if assets else state.status if state else None,
            freshness=freshness,
            last_checked_at=effective_checked,
        )
        quality = "ERROR" if errors else "WARNING" if updated else "VALIDATED" if assets else connector["quality_status"]
        connector.update(
            {
                "status": status,
                "status_label": STATUS_LABELS[status],
                "quality_status": quality,
                "quality_label": QUALITY_LABELS.get(quality, "Por revisar"),
                "freshness_status": freshness,
                "source_cutoff_date": _as_iso(effective_cutoff),
                "last_checked_at": _as_iso(effective_checked),
                "last_success_at": connector["last_success_at"] or _as_iso(effective_checked if not errors else None),
                "last_change_detected_at": _as_iso(last_change) or connector["last_change_detected_at"],
                "record_count": int(record_count or connector["record_count"] or 0),
                "asset_count": len(assets),
                "updated_assets": updated,
                "error_assets": errors,
                "assets": [
                    {
                        "code": asset.dataset_code,
                        "name": asset.display_name,
                        "category": asset.category,
                        "status": asset.status,
                        "file_url": asset.file_url,
                        "last_checked_at": _as_iso(asset.last_checked_at),
                        "last_change_detected_at": _as_iso(asset.last_change_detected_at),
                    }
                    for asset in sorted(
                        assets,
                        key=lambda item: (
                            {"UPDATED": 0, "ERROR": 1, "UNKNOWN": 2, "UNCHANGED": 3}.get(item.status, 4),
                            item.display_name or item.dataset_code,
                        ),
                    )
                ],
            }
        )
        return connector

    @classmethod
    def summary(cls, db: Session) -> Dict[str, Any]:
        states = cls._state_map(db)
        connectors = [
            cls._local_police(db, states.get("POLICIA_JAMUNDI")),
            cls._apply_state(cls._base("POLICIA_NACIONAL"), states.get("POLICIA_NACIONAL")),
            cls._apply_state(cls._base("MINDEFENSA"), states.get("MINDEFENSA")),
            cls._apply_state(cls._base("SIEDCO_PUBLICO"), states.get("SIEDCO_PUBLICO")),
            cls._apply_state(cls._base("OBSERVATORIO_VALLE"), states.get("OBSERVATORIO_VALLE")),
        ]
        attention_statuses = {"ERROR", "NOT_CONNECTED", "UPDATE_AVAILABLE", "NEEDS_REVIEW", "EXPIRED"}
        timestamps = [item["last_checked_at"] for item in connectors if item["last_checked_at"]]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "connectors": connectors,
            "totals": {
                "total": len(connectors),
                "connected": sum(1 for item in connectors if item["status"] != "NOT_CONNECTED"),
                "automatic": sum(1 for item in connectors if item["update_mode"] != "MANUAL"),
                "attention": sum(1 for item in connectors if item["status"] in attention_statuses),
                "updates": sum(1 for item in connectors if item["status"] == "UPDATE_AVAILABLE"),
            },
            "last_checked_at": max(timestamps) if timestamps else None,
        }

    @staticmethod
    def record_heartbeat(db: Session, connector_code: str, payload: Dict[str, Any]) -> SourceConnectorState:
        state = db.query(SourceConnectorState).filter_by(connector_code=connector_code).first()
        if state is None:
            state = SourceConnectorState(connector_code=connector_code)
            db.add(state)
        for field in (
            "status",
            "quality_status",
            "period_label",
            "source_cutoff_date",
            "last_checked_at",
            "last_success_at",
            "last_change_detected_at",
            "record_count",
            "indicator_count",
            "warnings",
            "details",
        ):
            if field in payload:
                setattr(state, field, payload[field])
        db.commit()
        db.refresh(state)
        return state
