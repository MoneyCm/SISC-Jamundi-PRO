from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import get_optional_user, institutional_access, log_audit
from api.source_center import authorize_source_monitor
from db.models import User
from db.models_fiscalia_spoa import FiscaliaSpoaRecord, FiscaliaSpoaRun, FiscaliaSpoaSnapshot
from db.session import get_db


router = APIRouter()
DATASET_CONFIG = {
    "procesos": {"id": "dbdv-iihs", "entity": "proceso_anonimizado", "process": "proceso_anonimizado", "year": "a_o_hecho", "month": "mes_hecho"},
    "victimas": {"id": "hr73-zqjf", "entity": "id_victima_anonimizado", "process": "proceso_anonimizado", "year": "a_o_hecho_origen", "month": "mes_hecho_origen"},
    "procesados": {"id": "piva-db2c", "entity": "id_procesado_anonimizado", "process": "proceso_anonimizado", "year": "a_o_hecho_origen", "month": "mes_hecho_origen"},
}


class SpoaIngestBatch(BaseModel):
    run_id: str = Field(min_length=10, max_length=80)
    dataset_key: str = Field(max_length=20)
    dataset_id: str = Field(min_length=9, max_length=20)
    cutoff_date: date
    metadata_sha256: str = Field(min_length=64, max_length=64)
    payload_sha256: str = Field(min_length=64, max_length=64)
    schema_version: str = Field(min_length=8, max_length=32)
    source_row_count: Optional[int] = Field(default=None, ge=0)
    filtered_count: Optional[int] = Field(default=None, ge=0)
    valid_count: Optional[int] = Field(default=None, ge=0)
    discarded_count: Optional[int] = Field(default=None, ge=0)
    discard_reasons: Dict[str, int] = Field(default_factory=dict)
    rows: List[Dict[str, Any]] = Field(min_length=1, max_length=1000)

    @field_validator("dataset_key")
    @classmethod
    def known_dataset(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in DATASET_CONFIG:
            raise ValueError("Conjunto SPOA no reconocido")
        return normalized

    @field_validator("rows")
    @classmethod
    def bounded_rows(cls, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(json.dumps(value, ensure_ascii=True, default=str)) > 8_000_000:
            raise ValueError("Lote SPOA supera el tamaño permitido")
        return value


class SpoaRunCompletion(BaseModel):
    status: str = Field(default="COMPLETED", max_length=40)
    source_cutoff_date: Optional[date] = None
    datasets: Dict[str, Any] = Field(default_factory=dict)
    bulletin_path: Optional[str] = Field(default=None, max_length=1000)
    bulletin_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)

    @field_validator("datasets")
    @classmethod
    def bounded_datasets(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=True, default=str)) > 100_000:
            raise ValueError("Manifiesto de conjuntos demasiado grande")
        return value


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _record_key(row: Dict[str, Any], config: Dict[str, str]) -> str:
    entity = str(row.get(config["entity"]) or "").strip()
    process = str(row.get(config["process"]) or "").strip()
    delito = str(row.get("deli_id") or row.get("delito") or "").strip()
    return hashlib.sha256(f"{entity}|{process}|{delito}".encode("utf-8")).hexdigest()


@router.post("/ingest")
async def ingest_spoa_batch(
    payload: SpoaIngestBatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    config = DATASET_CONFIG[payload.dataset_key]
    if payload.dataset_id != config["id"]:
        raise HTTPException(status_code=422, detail="Identificador Socrata no corresponde al conjunto")
    mode = await authorize_source_monitor(request, current_user, "FISCALIA_SPOA_V3")
    run = db.query(FiscaliaSpoaRun).filter_by(id=payload.run_id).first()
    if run is None:
        run = FiscaliaSpoaRun(id=payload.run_id, status="IN_PROGRESS", source_cutoff_date=payload.cutoff_date)
        db.add(run)
        db.flush()
    snapshot = db.query(FiscaliaSpoaSnapshot).filter_by(
        dataset_id=payload.dataset_id,
        cutoff_date=payload.cutoff_date,
        payload_sha256=payload.payload_sha256,
    ).first()
    if snapshot is None:
        snapshot = FiscaliaSpoaSnapshot(
            run_id=run.id,
            dataset_key=payload.dataset_key,
            dataset_id=payload.dataset_id,
            cutoff_date=payload.cutoff_date,
            metadata_sha256=payload.metadata_sha256,
            payload_sha256=payload.payload_sha256,
            schema_version=payload.schema_version,
            source_row_count=payload.source_row_count,
            filtered_count=payload.filtered_count or 0,
            valid_count=payload.valid_count or 0,
            discarded_count=payload.discarded_count or 0,
            discard_reasons=payload.discard_reasons,
        )
        db.add(snapshot)
        db.flush()

    values = []
    for row in payload.rows:
        entity = str(row.get(config["entity"]) or "").strip()
        if not entity:
            continue
        key = _record_key(row, config)
        values.append({
            "snapshot_id": snapshot.id,
            "dataset_key": payload.dataset_key,
            "record_key": key,
            "entity_anonimizado": entity,
            "proceso_anonimizado": str(row.get(config["process"]) or "").strip() or None,
            "delito_id": str(row.get("deli_id") or "").strip() or None,
            "delito": str(row.get("delito") or "").strip() or None,
            "year_hecho": _as_int(row.get(config["year"])),
            "month_hecho": _as_int(row.get(config["month"])),
            "estado": str(row.get("estado") or "").strip() or None,
            "etapa": str(row.get("etapa") or "").strip() or None,
            "payload": row,
        })
    try:
        inserted = 0
        if values:
            statement = insert(FiscaliaSpoaRecord).values(values).on_conflict_do_nothing(
                constraint="uq_spoa_snapshot_record"
            )
            result = db.execute(statement)
            inserted = max(int(result.rowcount or 0), 0)
        duplicated = len(values) - inserted
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto idempotente durante la ingesta")
    await log_audit(
        db,
        "FISCALIA_SPOA_BATCH_INGEST",
        actor_id=str(current_user.id) if current_user else None,
        module="FISCALIA_SPOA",
        target={"run_id": run.id, "dataset": payload.dataset_key, "inserted": inserted, "mode": mode},
        level=2,
        request=request,
    )
    return {"accepted": True, "snapshot_id": str(snapshot.id), "inserted": inserted, "duplicated": duplicated}


@router.post("/runs/{run_id}/complete")
async def complete_spoa_run(
    run_id: str,
    payload: SpoaRunCompletion,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    await authorize_source_monitor(request, current_user, "FISCALIA_SPOA_V3")
    run = db.query(FiscaliaSpoaRun).filter_by(id=run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Ejecución SPOA no encontrada")
    run.status = payload.status.strip().upper()
    run.finished_at = datetime.now(timezone.utc)
    run.source_cutoff_date = payload.source_cutoff_date or run.source_cutoff_date
    run.datasets = payload.datasets
    run.bulletin_path = payload.bulletin_path
    run.bulletin_sha256 = payload.bulletin_sha256
    db.commit()
    return {"accepted": True, "run_id": run.id, "status": run.status}


@router.get("/summary")
def spoa_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    result = []
    for key in DATASET_CONFIG:
        snapshot = db.query(FiscaliaSpoaSnapshot).filter_by(dataset_key=key).order_by(
            FiscaliaSpoaSnapshot.cutoff_date.desc(), FiscaliaSpoaSnapshot.created_at.desc()
        ).first()
        if snapshot:
            unique_entities = db.query(FiscaliaSpoaRecord.entity_anonimizado).filter_by(
                snapshot_id=snapshot.id
            ).distinct().count()
            result.append({
                "dataset_key": key,
                "dataset_id": snapshot.dataset_id,
                "cutoff_date": snapshot.cutoff_date,
                "unique_entities": unique_entities,
                "payload_sha256": snapshot.payload_sha256,
                "schema_version": snapshot.schema_version,
            })
    return {"generated_at": datetime.now(timezone.utc), "datasets": result}
