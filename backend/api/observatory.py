"""Centro de Análisis del Observatorio: portada, estudios y recomendaciones."""
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.auth import institutional_access, log_audit, require_role
from db.models import User, get_db
from db.models_council import CouncilCommitment
from db.models_observatory import (
    ACCESS_LEVELS, PRIORITIES, RECOMMENDATION_STATUSES, STUDY_STATUSES,
    ObservatoryRecommendation, ObservatoryStudy,
)
from services import observatory_service as service

router = APIRouter()

ANALYSIS_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]


def _sees_reserved(user: User) -> bool:
    return bool({role.code for role in (user.roles or [])} & set(ANALYSIS_ROLES))


class StudyIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=200)
    question: str = Field(min_length=10, max_length=2000)
    phenomenon: Optional[str] = Field(default=None, max_length=120)
    territory: Optional[str] = Field(default=None, max_length=200)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    sources: List[str] = Field(default_factory=list, max_length=20)
    hypotheses: Optional[str] = Field(default=None, max_length=5000)
    findings: Optional[str] = Field(default=None, max_length=20000)
    status: str = "ABIERTO"
    access_level: str = "INSTITUCIONAL"


class StudyUpdate(StudyIn):
    expected_version: int = Field(ge=0)


class RecommendationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    study_id: Optional[UUID] = None
    title: str = Field(min_length=3, max_length=200)
    text: str = Field(min_length=10, max_length=5000)
    addressed_to: Optional[str] = Field(default=None, max_length=200)
    priority: str = "MEDIA"
    due_date: Optional[date] = None


class RecommendationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str
    expected_version: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=2000)
    on_date: Optional[date] = None
    commitment_code: Optional[str] = Field(default=None, max_length=40)


def _check_study(payload: StudyIn):
    if payload.status not in STUDY_STATUSES:
        raise HTTPException(422, f"Estado no válido. Use: {', '.join(STUDY_STATUSES)}.")
    if payload.access_level not in ACCESS_LEVELS:
        raise HTTPException(422, f"Nivel de acceso no válido. Use: {', '.join(ACCESS_LEVELS)}.")
    if payload.period_start and payload.period_end and payload.period_start > payload.period_end:
        raise HTTPException(422, "El periodo termina antes de empezar.")
    if payload.status == "CERRADO" and not (payload.findings or "").strip():
        raise HTTPException(422, "Un estudio se cierra con sus hallazgos escritos.")


def serialize_study(row: ObservatoryStudy, recommendations: Optional[list] = None) -> dict:
    data = {
        "id": str(row.id), "code": row.code, "title": row.title, "question": row.question,
        "phenomenon": row.phenomenon, "territory": row.territory,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "sources": row.sources or [], "hypotheses": row.hypotheses, "findings": row.findings,
        "status": row.status, "access_level": row.access_level, "version": row.version,
        "created_by": row.created_by, "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if recommendations is not None:
        data["recommendations"] = [serialize_recommendation(item) for item in recommendations]
    return data


def serialize_recommendation(row: ObservatoryRecommendation, study_code: Optional[str] = None) -> dict:
    return {
        "id": str(row.id), "code": row.code, "study_id": str(row.study_id) if row.study_id else None,
        "study_code": study_code, "title": row.title, "text": row.text, "addressed_to": row.addressed_to,
        "priority": row.priority, "status": row.status,
        "presented_on": row.presented_on.isoformat() if row.presented_on else None,
        "decided_on": row.decided_on.isoformat() if row.decided_on else None,
        "decision_note": row.decision_note, "commitment_code": row.commitment_code,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "history": row.history or [], "version": row.version, "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _visible_study(db: Session, study_id: UUID, user: User) -> ObservatoryStudy:
    row = db.get(ObservatoryStudy, study_id)
    if not row or (row.access_level == "RESERVADO" and not _sees_reserved(user)):
        raise HTTPException(404, "Estudio no encontrado.")
    return row


@router.get("/overview")
def get_overview(db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    return service.overview(db, include_reserved=_sees_reserved(user))


@router.get("/studies")
def list_studies(status: Optional[str] = Query(default=None), db: Session = Depends(get_db),
                 user: User = Depends(institutional_access)):
    query = db.query(ObservatoryStudy)
    if not _sees_reserved(user):
        query = query.filter(ObservatoryStudy.access_level != "RESERVADO")
    if status:
        query = query.filter(ObservatoryStudy.status == status)
    rows = query.order_by(ObservatoryStudy.created_at.desc()).all()
    counts = {}
    for study_id, in db.query(ObservatoryRecommendation.study_id).filter(ObservatoryRecommendation.study_id.isnot(None)).all():
        counts[study_id] = counts.get(study_id, 0) + 1
    return [{**serialize_study(row), "recommendations_count": counts.get(row.id, 0)} for row in rows]


@router.get("/studies/{study_id}")
def get_study(study_id: UUID, db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    row = _visible_study(db, study_id, user)
    recommendations = db.query(ObservatoryRecommendation).filter_by(study_id=row.id).order_by(ObservatoryRecommendation.code).all()
    return serialize_study(row, recommendations)


@router.post("/studies", status_code=201)
async def create_study(payload: StudyIn, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(require_role(ANALYSIS_ROLES))):
    _check_study(payload)
    row = ObservatoryStudy(code=service.next_code(db, ObservatoryStudy, "OBS"), created_by=user.username,
                           **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    await log_audit(db, "OBSERVATORY_STUDY_CREATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code}, level=1, request=request)
    return serialize_study(row, [])


@router.put("/studies/{study_id}")
async def update_study(study_id: UUID, payload: StudyUpdate, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(require_role(ANALYSIS_ROLES))):
    _check_study(payload)
    row = _visible_study(db, study_id, user)
    if row.version != payload.expected_version:
        raise HTTPException(409, "Otra persona modificó este estudio. Recárguelo antes de guardar.")
    for field, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, field, value)
    row.version += 1
    row.updated_by = user.username
    db.commit()
    db.refresh(row)
    await log_audit(db, "OBSERVATORY_STUDY_UPDATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code, "status": row.status}, level=1, request=request)
    recommendations = db.query(ObservatoryRecommendation).filter_by(study_id=row.id).order_by(ObservatoryRecommendation.code).all()
    return serialize_study(row, recommendations)


@router.get("/recommendations")
def list_recommendations(status: Optional[str] = Query(default=None), db: Session = Depends(get_db),
                         user: User = Depends(institutional_access)):
    query = db.query(ObservatoryRecommendation, ObservatoryStudy.code, ObservatoryStudy.access_level).outerjoin(
        ObservatoryStudy, ObservatoryStudy.id == ObservatoryRecommendation.study_id)
    if status:
        query = query.filter(ObservatoryRecommendation.status == status)
    reserved = _sees_reserved(user)
    return [serialize_recommendation(row, code)
            for row, code, access in query.order_by(ObservatoryRecommendation.created_at.desc()).all()
            if reserved or access != "RESERVADO"]


@router.post("/recommendations", status_code=201)
async def create_recommendation(payload: RecommendationIn, request: Request, db: Session = Depends(get_db),
                                user: User = Depends(require_role(ANALYSIS_ROLES))):
    if payload.priority not in PRIORITIES:
        raise HTTPException(422, f"Prioridad no válida. Use: {', '.join(PRIORITIES)}.")
    study_code = None
    if payload.study_id:
        study_code = _visible_study(db, payload.study_id, user).code
    row = ObservatoryRecommendation(
        code=service.next_code(db, ObservatoryRecommendation, "REC"), created_by=user.username,
        history=[_event(user, "PROPUESTA", "Redactada")], **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    await log_audit(db, "OBSERVATORY_RECOMMENDATION_CREATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code, "study": study_code}, level=1, request=request)
    return serialize_recommendation(row, study_code)


def _event(user: User, status: str, note: Optional[str]) -> dict:
    return {"status": status, "note": note, "by": user.username, "at": datetime.now(timezone.utc).isoformat()}


# Una recomendación avanza en este orden; RECHAZADA cierra el camino.
ALLOWED_TRANSITIONS = {
    "PROPUESTA": {"PRESENTADA"},
    "PRESENTADA": {"ACEPTADA", "RECHAZADA"},
    "ACEPTADA": {"EN_EJECUCION", "CUMPLIDA"},
    "EN_EJECUCION": {"CUMPLIDA"},
    "RECHAZADA": set(),
    "CUMPLIDA": set(),
}


@router.post("/recommendations/{rec_id}/status")
async def change_recommendation_status(rec_id: UUID, payload: RecommendationStatus, request: Request,
                                       db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    row = db.get(ObservatoryRecommendation, rec_id)
    if not row:
        raise HTTPException(404, "Recomendación no encontrada.")
    if row.version != payload.expected_version:
        raise HTTPException(409, "Otra persona modificó esta recomendación. Recárguela.")
    if payload.status not in RECOMMENDATION_STATUSES:
        raise HTTPException(422, "Estado no válido.")
    if payload.status not in ALLOWED_TRANSITIONS[row.status]:
        allowed = ", ".join(sorted(ALLOWED_TRANSITIONS[row.status])) or "ninguno (está cerrada)"
        raise HTTPException(422, f"De {row.status} solo se puede pasar a: {allowed}.")
    on_date = payload.on_date or date.today()
    if on_date > date.today():
        raise HTTPException(422, "La fecha no puede ser futura.")
    if payload.status in ("ACEPTADA", "RECHAZADA") and not (payload.note or "").strip():
        raise HTTPException(422, "Escriba quién decidió y en qué instancia (p. ej. Consejo de Seguridad del 12/09).")
    code = (payload.commitment_code or "").strip().upper() or None
    if code:
        if not db.query(CouncilCommitment.id).filter(CouncilCommitment.code == code).first():
            raise HTTPException(422, f"No existe el compromiso {code}.")
        row.commitment_code = code
    if payload.status == "EN_EJECUCION" and not row.commitment_code:
        raise HTTPException(422, "Para pasar a ejecución, enlace el compromiso que la ejecuta.")
    if payload.status == "PRESENTADA":
        row.presented_on = on_date
    if payload.status in ("ACEPTADA", "RECHAZADA"):
        row.decided_on = on_date
        row.decision_note = payload.note
    row.status = payload.status
    row.history = [*(row.history or []), {**_event(user, payload.status, payload.note), "on": on_date.isoformat(),
                                          "commitment_code": code}]
    row.version += 1
    row.updated_by = user.username
    db.commit()
    db.refresh(row)
    await log_audit(db, "OBSERVATORY_RECOMMENDATION_STATUS", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code, "status": row.status, "commitment": row.commitment_code}, level=1, request=request)
    study_code = db.query(ObservatoryStudy.code).filter(ObservatoryStudy.id == row.study_id).scalar() if row.study_id else None
    return serialize_recommendation(row, study_code)
