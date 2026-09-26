"""Compromisos de los Consejos de Seguridad: consulta, seguimiento e importación."""
import zipfile
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.auth import institutional_access, log_audit, require_role
from db.models import User, get_db
from db.models_council import COMMITMENT_STATUSES, CouncilCommitment, CouncilCommitmentUpdate
from services import council_commitments_service as service
from services.act_reader import INSTANCES

router = APIRouter()

# Opción (a): el equipo de la Secretaría actualiza el seguimiento.
FOLLOWUP_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str
    expected_version: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=2000)
    evidence_url: Optional[str] = Field(default=None, max_length=1000)
    deadline_date: Optional[date] = None


def _all(db: Session):
    return db.query(CouncilCommitment).order_by(CouncilCommitment.origin_date.desc().nullslast(), CouncilCommitment.code).all()


class ProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    index: int = Field(ge=0)
    action: str = Field(pattern="^(CREATE|LINK|SKIP)$")
    text: Optional[str] = Field(default=None, max_length=4000)
    responsible: Optional[str] = Field(default=None, max_length=300)
    deadline_date: Optional[date] = None
    link_code: Optional[str] = Field(default=None, max_length=40)


class RereadLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=0)
    link_code: Optional[str] = Field(default=None, max_length=40)


class ConfirmAct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: List[ProposalDecision] = Field(default_factory=list, max_length=200)
    reread_links: List[RereadLink] = Field(default_factory=list, max_length=100)


@router.get("/instances")
def list_instances(db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    counts = {}
    for row in _all(db):
        counts[row.instance or "CONSEJO_SEGURIDAD"] = counts.get(row.instance or "CONSEJO_SEGURIDAD", 0) + 1
    return [{"code": code, "label": data["label"], "count": counts.get(code, 0)} for code, data in INSTANCES.items()]


@router.post("/acts/read")
async def read_act_endpoint(
    request: Request,
    file: UploadFile = File(...),
    instance: Optional[str] = Form(default=None),
    use_ocr: bool = Form(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    """Lee un acta (Word o PDF) y devuelve propuestas de compromisos para revisión. No guarda compromisos.

    use_ocr: autorización explícita para enviar un PDF escaneado a Gemini y transcribirlo.
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "El archivo está vacío.")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "El archivo supera 25 MB.")
    try:
        result = service.read_act_for_review(db, content, file.filename or "acta", instance, current_user.username,
                                             use_ocr=use_ocr)
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        raise HTTPException(422, f"No se pudo leer el acta: {error}") from error
    except RuntimeError as error:
        raise HTTPException(502, f"No se pudo leer el acta escaneada con OCR: {error}") from error
    await log_audit(db, "COUNCIL_ACT_READ", actor_id=str(current_user.id), module="COUNCIL",
                    target={"filename": file.filename, "instance": result.get("instance"),
                            "proposals": len(result.get("proposals", []))}, level=1, request=request)
    return result


@router.get("/recurrence")
def commitments_recurrence(db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    return service.recurrence(db)


@router.post("/acts/history")
async def store_historical_act(
    request: Request,
    file: UploadFile = File(...),
    use_ocr: bool = Form(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    """Acta de años anteriores: se guarda solo para medir qué temas vuelven; no crea compromisos."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "El archivo está vacío.")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "El archivo supera 25 MB.")
    try:
        result = service.store_historical_act(db, content, file.filename or "acta", current_user.username, use_ocr=use_ocr)
    except (ValueError, KeyError, zipfile.BadZipFile) as error:
        raise HTTPException(422, f"No se pudo leer el acta: {error}") from error
    except RuntimeError as error:
        raise HTTPException(502, f"No se pudo leer el acta escaneada con OCR: {error}") from error
    await log_audit(db, "COUNCIL_ACT_HISTORICAL", actor_id=str(current_user.id), module="COUNCIL",
                    target={"filename": file.filename, "duplicate": result.get("duplicate")}, level=1, request=request)
    return result


@router.get("/acts")
def list_act_reads(
    status: Optional[str] = Query(default="PENDIENTE", pattern="^(PENDIENTE|CONFIRMADA|HISTORICA)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    return service.list_act_reads(db, status)


@router.get("/acts/{read_id}")
def open_act_read(read_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(FOLLOWUP_ROLES))):
    try:
        return service.open_act_read(db, read_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.delete("/acts/{read_id}")
async def discard_act_read(
    read_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    try:
        service.discard_act_read(db, read_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    await log_audit(db, "COUNCIL_ACT_DISCARDED", actor_id=str(current_user.id), module="COUNCIL",
                    target={"read_id": read_id}, level=1, request=request)
    return {"ok": True}


@router.post("/acts/{read_id}/confirm")
async def confirm_act_endpoint(
    read_id: str,
    payload: ConfirmAct,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    try:
        result = service.confirm_act(
            db, read_id, [item.model_dump(mode="json") for item in payload.decisions],
            [item.model_dump() for item in payload.reread_links], current_user.username,
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error)) from error
    await log_audit(db, "COUNCIL_ACT_CONFIRMED", actor_id=str(current_user.id), module="COUNCIL",
                    target={"read_id": read_id, **{key: len(value) if isinstance(value, list) else value for key, value in result.items()}},
                    level=1, request=request)
    return result


@router.get("/")
def list_commitments(
    status: Optional[str] = None,
    theme: Optional[str] = None,
    instance: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=120),
    flag: Optional[str] = Query(default=None, pattern="^(ATRASADO|REPETIDO|SIN_FECHA|SIN_INFORMACION)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    query = db.query(CouncilCommitment)
    if status:
        query = query.filter(CouncilCommitment.status == status)
    if theme:
        query = query.filter(CouncilCommitment.theme == theme)
    if instance:
        query = query.filter(CouncilCommitment.instance == instance)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(CouncilCommitment.text.ilike(like), CouncilCommitment.responsible.ilike(like),
                                 CouncilCommitment.code.ilike(like), CouncilCommitment.territory.ilike(like)))
    items = [service.serialize(row) for row in query.order_by(CouncilCommitment.origin_date.desc().nullslast(), CouncilCommitment.code).all()]
    if flag:
        items = [item for item in items if flag in item["flags"]]
    return {"items": items, "themes": sorted({row.theme for row in _all(db) if row.theme}),
            "statuses": [{"code": code, "label": service.STATUS_LABELS[code]} for code in COMMITMENT_STATUSES],
            "instances": [{"code": code, "label": data["label"]} for code, data in INSTANCES.items()]}


@router.get("/summary")
def commitments_summary(db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    return service.summary(_all(db))


@router.get("/agenda")
def commitments_agenda(db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    return {"text": service.agenda_text(_all(db))}


def _decision_report(db: Session, instance: str, session_date: Optional[date]):
    from services.council_decision_report import build_report

    if instance not in INSTANCES:
        raise HTTPException(status_code=422, detail="Instancia no reconocida.")
    return build_report(db, instance, session_date)


@router.get("/decision-report")
def decision_report(instance: str = Query(default="CONSEJO_SEGURIDAD"), session_date: Optional[date] = Query(default=None),
                    db: Session = Depends(get_db), current_user: User = Depends(require_role(FOLLOWUP_ROLES))):
    """Informe para decisión de la instancia (reservado): qué requiere decisión y qué se cumplió."""
    return _decision_report(db, instance, session_date)


@router.get("/decision-report.pdf")
async def decision_report_pdf(request: Request, instance: str = Query(default="CONSEJO_SEGURIDAD"),
                              session_date: Optional[date] = Query(default=None), db: Session = Depends(get_db),
                              current_user: User = Depends(require_role(FOLLOWUP_ROLES))):
    from fastapi.responses import Response
    from services.council_decision_report_pdf import build_decision_report_pdf

    report = _decision_report(db, instance, session_date)
    pdf = build_decision_report_pdf(report)
    await log_audit(db, "COUNCIL_DECISION_REPORT", actor_id=str(current_user.id), module="COUNCIL",
                    target={"instance": instance, "session_date": report["session_date"]}, level=2, request=request)
    filename = f"informe-decision-{INSTANCES[instance]['prefix'].lower()}-{report['session_date']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/{code}/history")
def commitment_history(code: str, db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    row = db.query(CouncilCommitment).filter(CouncilCommitment.code == code).first()
    if not row:
        raise HTTPException(404, "Compromiso no encontrado.")
    updates = db.query(CouncilCommitmentUpdate).filter(CouncilCommitmentUpdate.commitment_id == row.id).order_by(
        CouncilCommitmentUpdate.version.desc()).all()
    return [{
        "version": item.version, "action": item.action,
        "previous_status": service.STATUS_LABELS.get(item.previous_status, item.previous_status),
        "new_status": service.STATUS_LABELS.get(item.new_status, item.new_status),
        "note": item.note, "evidence_url": item.evidence_url, "username": item.username,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    } for item in updates]


@router.patch("/{code}")
async def update_commitment(
    code: str,
    payload: StatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    try:
        row = service.update_status(
            db, code, status=payload.status, note=payload.note, evidence_url=payload.evidence_url,
            deadline_date=payload.deadline_date, expected_version=payload.expected_version,
            username=current_user.username,
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    await log_audit(db, "COUNCIL_COMMITMENT_UPDATED", actor_id=str(current_user.id), module="COUNCIL",
                    target={"code": code, "status": payload.status}, level=1, request=request)
    return service.serialize(row)


@router.post("/import")
async def import_commitments(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(FOLLOWUP_ROLES)),
):
    content = await file.read()
    if not content:
        raise HTTPException(400, "El archivo está vacío.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "El archivo supera 10 MB.")
    try:
        commitments = service.rows_from_file(content, file.filename or "")
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    result = service.import_commitments(db, commitments, current_user.username)
    await log_audit(db, "COUNCIL_COMMITMENTS_IMPORTED", actor_id=str(current_user.id), module="COUNCIL",
                    target={"filename": file.filename, **result}, level=1, request=request)
    return result
