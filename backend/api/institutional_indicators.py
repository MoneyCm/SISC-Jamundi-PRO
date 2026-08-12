from datetime import date, datetime
from decimal import Decimal
import hashlib
from pathlib import PurePath
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from db.models import User
from db.models_institutional import InstitutionalAgentFinding, InstitutionalAgentRun, InstitutionalDataBatch, InstitutionalIndicator
from db.session import get_db
from api.auth import get_current_user
from services.institutional_agent_service import InstitutionalAgentService

router = APIRouter()
PERIOD_PATTERN = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")

def _validate_temporal_metadata(period: str, cutoff: date):
    if cutoff > date.today():
        raise HTTPException(status_code=422, detail="La fecha de corte no puede estar en el futuro.")
    if period != cutoff.strftime("%Y-%m"):
        raise HTTPException(status_code=422, detail="El periodo debe coincidir con el mes y ano de la fecha de corte.")




class FindingResolution(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


class IndicatorInput(BaseModel):
    indicator: str = Field(min_length=3, max_length=220)
    category: Optional[str] = Field(default=None, max_length=160)
    value: Decimal = Field(ge=0)
    unit: str = Field(default="casos", min_length=1, max_length=40)
    is_public: bool = True
    privacy_threshold: int = Field(default=10, ge=1, le=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class BatchInput(BaseModel):
    program: str = Field(min_length=3, max_length=80)
    reporting_entity: str = Field(min_length=3, max_length=180)
    period: str = Field(min_length=7, max_length=7)
    cutoff_date: datetime
    reporting_basis: str = Field(default="CUMULATIVE", max_length=20)
    source_reference: str = Field(min_length=3, max_length=500)
    source_filename: Optional[str] = Field(default=None, max_length=255)
    version: int = Field(default=1, ge=1, le=99)
    indicators: List[IndicatorInput] = Field(min_length=1, max_length=100)


def _public_record(batch: InstitutionalDataBatch, indicator: InstitutionalIndicator):
    return {
        "program": batch.program,
        "reporting_entity": batch.reporting_entity,
        "period": batch.period,
        "cutoff_date": batch.cutoff_date.isoformat(),
        "reporting_basis": batch.reporting_basis,
        "indicator": indicator.indicator,
        "category": indicator.category,
        "value": float(indicator.value),
        "unit": indicator.unit,
        "source_reference": batch.source_reference,
        "version": batch.version,
    }


@router.post("/batches", status_code=201)
def create_batch(payload: BatchInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reporting_basis = payload.reporting_basis.strip().upper()
    canonical_entity = InstitutionalAgentService.canonical_entity(payload.reporting_entity)
    _validate_temporal_metadata(payload.period, payload.cutoff_date.date())
    if reporting_basis not in {"MONTHLY", "CUMULATIVE"}:
        raise HTTPException(status_code=422, detail="La modalidad debe ser MONTHLY o CUMULATIVE.")
    if not PERIOD_PATTERN.match(payload.period):
        raise HTTPException(status_code=422, detail="El periodo debe tener formato AAAA-MM.")

    for item in payload.indicators:
        if item.is_public and item.value < item.privacy_threshold:
            raise HTTPException(
                status_code=422,
                detail=f"El indicador '{item.indicator}' esta por debajo del umbral de privacidad y debe cargarse como no publico.",
            )

    duplicate = db.query(InstitutionalDataBatch).filter_by(
        program=payload.program.strip(),
        reporting_entity=canonical_entity,
        period=payload.period,
        version=payload.version,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe una carga para esta dependencia, periodo y version.")

    batch = InstitutionalDataBatch(
        program=payload.program.strip(),
        reporting_entity=canonical_entity,
        period=payload.period,
        cutoff_date=payload.cutoff_date.date(),
        reporting_basis=reporting_basis,
        source_reference=payload.source_reference.strip(),
        source_filename=payload.source_filename,
        version=payload.version,
        validation_status="PENDING",
        submitted_by=str(current_user.id),
    )
    batch.indicators = [
        InstitutionalIndicator(
            indicator=item.indicator.strip(),
            category=item.category.strip() if item.category else None,
            value=item.value,
            unit=item.unit.strip(),
            is_public=item.is_public,
            privacy_threshold=item.privacy_threshold,
            notes=item.notes.strip() if item.notes else None,
        )
        for item in payload.indicators
    ]
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {"id": str(batch.id), "status": batch.validation_status, "records": len(batch.indicators)}


@router.post("/batches/{batch_id}/approve")
def approve_batch(batch_id: str, notes: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    batch = db.query(InstitutionalDataBatch).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Carga no encontrada.")

    _validate_temporal_metadata(batch.period, batch.cutoff_date)
    source_hint = InstitutionalAgentService(db).detect_metadata(b"", batch.source_filename or "")
    if source_hint.get("period") and source_hint["period"] != batch.period:
        raise HTTPException(status_code=409, detail="El periodo no coincide con el mes y ano identificados en el nombre del archivo.")

    unresolved = db.query(InstitutionalAgentFinding).join(InstitutionalAgentRun).filter(
        InstitutionalAgentRun.batch_id == batch.id,
        InstitutionalAgentFinding.blocks_publication.is_(True),
        InstitutionalAgentFinding.resolved.is_(False),
    ).count()
    if unresolved:
        raise HTTPException(status_code=409, detail=f"La carga tiene {unresolved} hallazgos bloqueantes sin resolver.")
    approved_peers = db.query(InstitutionalDataBatch).filter(
        InstitutionalDataBatch.program == batch.program,
        InstitutionalDataBatch.period == batch.period,
        InstitutionalDataBatch.validation_status == "APPROVED",
        InstitutionalDataBatch.id != batch.id,
    ).all()
    canonical_batch_entity = InstitutionalAgentService.canonical_entity(batch.reporting_entity)
    for peer in approved_peers:
        if InstitutionalAgentService.canonical_entity(peer.reporting_entity) == canonical_batch_entity:
            peer.validation_status = "SUPERSEDED"
    batch.validation_status = "APPROVED"
    batch.approved_by = str(current_user.id)
    batch.approved_at = datetime.utcnow()
    batch.review_notes = notes
    db.commit()
    return {"id": str(batch.id), "status": batch.validation_status}




@router.post("/agent-detect")
async def agent_detect(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo esta vacio.")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera el limite de 25 MB.")
    return InstitutionalAgentService(db).detect_metadata(content, file.filename or "archivo_sin_nombre")

@router.post("/agent-ingest", status_code=201)
async def agent_ingest(
    file: UploadFile = File(...),
    program: str = Form(...),
    reporting_entity: str = Form(...),
    period: str = Form(...),
    cutoff_date: date = Form(...),
    reporting_basis: str = Form("CUMULATIVE"),
    version: int = Form(1),
    use_cloud_ocr: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reporting_basis = reporting_basis.strip().upper()
    program = program.strip().upper()
    reporting_entity = InstitutionalAgentService.canonical_entity(reporting_entity)
    ocr_pdf = PurePath(file.filename or "").suffix.lower() == ".pdf" and use_cloud_ocr
    if not ocr_pdf:
        _validate_temporal_metadata(period, cutoff_date)
    if reporting_basis not in {"MONTHLY", "CUMULATIVE"}:
        raise HTTPException(status_code=422, detail="La modalidad debe ser MONTHLY o CUMULATIVE.")
    if not PERIOD_PATTERN.match(period):
        raise HTTPException(status_code=422, detail="El periodo debe tener formato AAAA-MM.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo esta vacio.")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera el limite de 25 MB.")
    agent_service = InstitutionalAgentService(db)
    detected = agent_service.detect_metadata(content, file.filename or "archivo_sin_nombre")
    if not ocr_pdf:
        if detected.get("program") and detected["program"] != program:
            raise HTTPException(status_code=422, detail=f"El archivo corresponde a {detected['program']} y no a {program}.")
        if detected.get("reporting_entity") and InstitutionalAgentService.canonical_entity(detected["reporting_entity"]) != reporting_entity:
            raise HTTPException(status_code=422, detail=f"La dependencia detectada es {detected['reporting_entity']}.")
        if detected.get("period") and detected["period"] != period:
            raise HTTPException(status_code=422, detail=f"El periodo detectado es {detected['period']} y no {period}.")
    source_hash = hashlib.sha256(content).hexdigest()
    existing = db.query(InstitutionalAgentRun).filter_by(source_sha256=source_hash, extractor_version=InstitutionalAgentService.EXTRACTOR_VERSION).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Este archivo ya fue procesado en la ejecucion {existing.id}.")
    latest_batch = db.query(InstitutionalDataBatch).filter_by(
        program=program.strip(), reporting_entity=reporting_entity.strip(), period=period
    ).order_by(InstitutionalDataBatch.version.desc()).first()
    if latest_batch and version <= latest_batch.version:
        version = latest_batch.version + 1
    run = agent_service.ingest(
        content, file.filename or "archivo_sin_nombre", program, reporting_entity,
        period, cutoff_date, reporting_basis, version, str(current_user.id), use_cloud_ocr
    )
    return agent_run_detail(str(run.id), db, current_user)


@router.get("/agent-runs/{run_id}")
def agent_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(InstitutionalAgentRun).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Ejecucion no encontrada.")
    batch = run.batch
    return {
        "id": str(run.id),
        "status": run.status,
        "source_filename": run.source_filename,
        "source_sha256": run.source_sha256,
        "summary": run.summary,
        "batch": None if not batch else {
            "id": str(batch.id),
            "status": batch.validation_status,
            "program": batch.program,
            "reporting_entity": batch.reporting_entity,
            "period": batch.period,
            "indicators": [
                {
                    "id": str(item.id), "indicator": item.indicator, "value": float(item.value),
                    "unit": item.unit, "is_public": item.is_public,
                }
                for item in batch.indicators
            ],
        },
        "findings": [
            {
                "id": str(item.id), "agent": item.agent_name, "severity": item.severity,
                "code": item.code, "message": item.message, "evidence": item.evidence,
                "blocks_publication": item.blocks_publication, "resolved": item.resolved,
            }
            for item in run.findings
        ],
    }


@router.post("/agent-findings/{finding_id}/resolve")
def resolve_finding(
    finding_id: str,
    payload: FindingResolution,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    finding = db.query(InstitutionalAgentFinding).filter_by(id=finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado.")
    finding.resolved = True
    finding.resolved_by = str(current_user.id)
    finding.resolved_at = datetime.utcnow()
    if payload.note:
        finding.message = f"{finding.message}\nResolucion: {payload.note.strip()}"
    run = finding.run
    if run and all(item.resolved or not item.blocks_publication for item in run.findings):
        run.status = "READY_FOR_APPROVAL"
    db.commit()
    return {"id": str(finding.id), "resolved": True, "run_status": run.status if run else None}

@router.post("/batches/{batch_id}/reject")
def reject_batch(batch_id: str, notes: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    batch = db.query(InstitutionalDataBatch).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Carga no encontrada.")
    if batch.validation_status != "PENDING":
        raise HTTPException(status_code=409, detail="Solo se pueden rechazar cargas pendientes.")
    batch.validation_status = "REJECTED"
    batch.review_notes = notes or "Rechazado desde la mesa de revision institucional."
    db.commit()
    return {"id": str(batch.id), "status": batch.validation_status}

@router.get("/public")
def public_indicators(program: Optional[str] = None, reporting_entity: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(InstitutionalDataBatch, InstitutionalIndicator).join(
        InstitutionalIndicator, InstitutionalIndicator.batch_id == InstitutionalDataBatch.id
    ).filter(
        InstitutionalDataBatch.validation_status == "APPROVED",
        InstitutionalIndicator.is_public.is_(True),
        InstitutionalIndicator.value >= InstitutionalIndicator.privacy_threshold,
    )
    if program:
        query = query.filter(InstitutionalDataBatch.program == program)
    if reporting_entity:
        query = query.filter(InstitutionalDataBatch.reporting_entity == reporting_entity)
    rows = query.order_by(InstitutionalDataBatch.period.desc(), InstitutionalIndicator.indicator.asc()).all()
    return {"records": [_public_record(batch, indicator) for batch, indicator in rows]}


@router.get("/batches")
def list_batches(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    batches = db.query(InstitutionalDataBatch).order_by(InstitutionalDataBatch.created_at.desc()).all()
    items = []
    for batch in batches:
        run = db.query(InstitutionalAgentRun).filter_by(batch_id=batch.id).first()
        items.append({
            "id": str(batch.id),
            "program": batch.program,
            "reporting_entity": batch.reporting_entity,
            "period": batch.period,
            "cutoff_date": batch.cutoff_date.isoformat(),
            "reporting_basis": batch.reporting_basis,
            "status": batch.validation_status,
            "version": batch.version,
            "records": len(batch.indicators),
            "source_filename": batch.source_filename,
            "agent_run_id": str(run.id) if run else None,
        })
    return {"batches": items}