"""Centro de Análisis del Observatorio: portada, estudios y recomendaciones."""
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import institutional_access, log_audit, require_role
from db.models import User, get_db
from db.models_council import CouncilCommitment
from db.models_observatory import (
    ACCESS_LEVELS, FIELD_NOTE_KINDS, MAX_OPEN_STUDIES, OPEN_STUDY_STATUSES, PRIORITIES,
    RECOMMENDATION_STATUSES, STUDY_STATUSES,
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
    associated_factors: Optional[str] = Field(default=None, max_length=10000)
    review_on: Optional[date] = None
    status_note: Optional[str] = Field(default=None, max_length=2000)
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
    if payload.status == "PAUSADO" and not (payload.status_note or "").strip():
        raise HTTPException(422, "Escriba por qué se pausa el estudio.")


def _check_open_limit(db: Session, status: str, exclude_id=None) -> None:
    """Tope de estudios abiertos: para abrir otro hay que cerrar o pausar uno, de forma explícita."""
    if status not in OPEN_STUDY_STATUSES:
        return
    query = db.query(ObservatoryStudy.code).filter(ObservatoryStudy.status.in_(OPEN_STUDY_STATUSES))
    if exclude_id is not None:
        query = query.filter(ObservatoryStudy.id != exclude_id)
    codes = [code for (code,) in query.order_by(ObservatoryStudy.code).all()]
    if len(codes) >= MAX_OPEN_STUDIES:
        raise HTTPException(409, f"Ya hay {len(codes)} estudios abiertos ({', '.join(codes)}), el tope del Observatorio. "
                                 "Cierre o pause uno, con su motivo, antes de abrir otro.")


def serialize_study(row: ObservatoryStudy, recommendations: Optional[list] = None) -> dict:
    data = {
        "id": str(row.id), "code": row.code, "title": row.title, "question": row.question,
        "phenomenon": row.phenomenon, "territory": row.territory,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "sources": row.sources or [], "hypotheses": row.hypotheses, "findings": row.findings,
        "associated_factors": row.associated_factors,
        "review_on": row.review_on.isoformat() if row.review_on else None,
        "status_note": row.status_note, "field_notes": row.field_notes or [],
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


@router.get("/piscc-goals")
def get_piscc_goals(db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    """Metas de resultado del PISCC (tabla 16) frente a lo corrido del año, cada una con su fuente y corte."""
    from services.piscc_goals import build_goals

    return build_goals(db)


class PisccReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    value: Optional[float] = Field(default=None, ge=0)
    status: str = "EN_EJECUCION"
    reporting_entity: Optional[str] = Field(default=None, max_length=200)
    evidence: Optional[str] = Field(default=None, max_length=2000)
    note: Optional[str] = Field(default=None, max_length=2000)
    received_on: Optional[date] = None
    expected_version: Optional[int] = Field(default=None, ge=0)  # None = primer reporte del semestre


def _piscc_semester(semester: Optional[str]) -> str:
    from services import piscc_actions

    semester = semester or piscc_actions.semester_of(date.today())
    if not piscc_actions.valid_semester(semester):
        raise HTTPException(422, "Semestre fuera del PISCC 2024-2027. Use el formato 2026-1 o 2026-2.")
    return semester


@router.get("/piscc-actions")
def get_piscc_actions(semester: Optional[str] = Query(default=None), db: Session = Depends(get_db),
                      user: User = Depends(institutional_access)):
    """Plan de acción del PISCC: avance de las 43 acciones en el semestre, por vector y entidad."""
    from services.piscc_actions import build_tracking

    return build_tracking(db, _piscc_semester(semester))


@router.get("/piscc-actions/export")
def export_piscc_actions(semester: Optional[str] = Query(default=None), db: Session = Depends(get_db),
                         user: User = Depends(institutional_access)):
    """CSV del seguimiento semestral, para el reporte al SisPT."""
    from fastapi.responses import Response
    from services.piscc_actions import build_tracking, export_csv

    semester = _piscc_semester(semester)
    return Response(export_csv(build_tracking(db, semester)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="PISCC_seguimiento_{semester}.csv"'})


@router.put("/piscc-actions/{code}/{semester}")
async def save_piscc_report(code: str, semester: str, payload: PisccReportIn, request: Request,
                            db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    from db.models_piscc import ACTION_STATUSES, PisccActionReport
    from services.piscc_actions import load_catalog

    semester = _piscc_semester(semester)
    if code not in {item["code"] for item in load_catalog()["actions"]}:
        raise HTTPException(404, "La acción no existe en el plan de acción del PISCC.")
    if payload.status not in ACTION_STATUSES:
        raise HTTPException(422, f"Estado no válido. Use: {', '.join(ACTION_STATUSES)}.")
    row = db.query(PisccActionReport).filter_by(action_code=code, semester=semester).first()
    if row is None:
        if payload.expected_version is not None:
            raise HTTPException(409, "El reporte que editaba ya no existe. Recargue la página.")
        row = PisccActionReport(action_code=code, semester=semester, created_by=user.username)
        db.add(row)
    elif row.version != payload.expected_version:
        raise HTTPException(409, "Otra persona modificó este reporte. Recárguelo antes de guardar.")
    else:
        row.version += 1
        row.updated_by = user.username
    for field, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    await log_audit(db, "PISCC_ACTION_REPORT_SAVED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"action": code, "semester": semester, "value": row.value, "status": row.status},
                    level=1, request=request)
    from services.piscc_actions import serialize_report
    return serialize_report(row)


class DataRequestsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    entity_ids: List[UUID] = Field(min_length=1, max_length=50)
    what: str = Field(min_length=3, max_length=300)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    requested_on: date
    due_on: Optional[date] = None
    channel: Optional[str] = Field(default=None, max_length=60)


class DataRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str
    received_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    expected_version: int = Field(ge=0)


class DataEntityIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=3, max_length=200)
    program: str = "OTRA"
    cadence: str = "SEMANAL"
    contact: Optional[str] = Field(default=None, max_length=300)
    active: bool = True


def _check_entity(payload: DataEntityIn) -> None:
    from db.models_data_requests import CADENCES, PROGRAMS

    if payload.program not in PROGRAMS:
        raise HTTPException(422, f"Programa no válido. Use: {', '.join(PROGRAMS)}.")
    if payload.cadence not in CADENCES:
        raise HTTPException(422, f"Periodicidad no válida. Use: {', '.join(CADENCES)}.")


@router.get("/data-requests")
def get_data_requests(db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Solicitudes de datos a Inspecciones, Comisarías y otras dependencias, con su estado."""
    from services.data_requests import board

    return board(db, include_inactive=True)


@router.post("/data-requests", status_code=201)
async def create_data_requests(payload: DataRequestsIn, request: Request, db: Session = Depends(get_db),
                               user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Registra la misma solicitud para varias dependencias (la rutina del lunes)."""
    from datetime import timedelta

    from db.models_data_requests import DataEntity, DataRequest
    from services.data_requests import DEFAULT_DUE_DAYS, serialize_request

    if payload.period_start and payload.period_end and payload.period_start > payload.period_end:
        raise HTTPException(422, "El periodo pedido empieza después de terminar.")
    due_on = payload.due_on or payload.requested_on + timedelta(days=DEFAULT_DUE_DAYS)
    if due_on < payload.requested_on:
        raise HTTPException(422, "El plazo no puede ser anterior a la fecha de la solicitud.")
    entities = db.query(DataEntity).filter(DataEntity.id.in_(payload.entity_ids)).all()
    if len(entities) != len(set(payload.entity_ids)):
        raise HTTPException(404, "Alguna dependencia no existe.")
    rows = []
    for entity in entities:
        row = DataRequest(entity_id=entity.id, what=payload.what, period_start=payload.period_start,
                          period_end=payload.period_end, requested_on=payload.requested_on, due_on=due_on,
                          channel=payload.channel, created_by=user.username)
        db.add(row)
        rows.append((row, entity.name))
    db.commit()
    await log_audit(db, "DATA_REQUESTS_CREATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"entities": [name for _, name in rows], "what": payload.what}, level=1, request=request)
    return [serialize_request(row, name) for row, name in rows]


@router.put("/data-requests/{request_id}")
async def update_data_request(request_id: UUID, payload: DataRequestUpdate, request: Request,
                              db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    from db.models_data_requests import REQUEST_STATUSES, DataEntity, DataRequest
    from services.data_requests import serialize_request

    if payload.status not in REQUEST_STATUSES:
        raise HTTPException(422, f"Estado no válido. Use: {', '.join(REQUEST_STATUSES)}.")
    row = db.get(DataRequest, request_id)
    if not row:
        raise HTTPException(404, "La solicitud no existe.")
    if row.version != payload.expected_version:
        raise HTTPException(409, "Otra persona modificó esta solicitud. Recargue la página.")
    received_on = payload.received_on
    if payload.status in ("RECIBIDA", "INCOMPLETA"):
        received_on = received_on or date.today()
        if received_on < row.requested_on:
            raise HTTPException(422, "La fecha de recibo no puede ser anterior a la solicitud.")
    else:
        received_on = None
    row.status, row.received_on, row.note = payload.status, received_on, payload.note
    row.version += 1
    row.updated_by = user.username
    db.commit()
    db.refresh(row)
    entity = db.get(DataEntity, row.entity_id)
    await log_audit(db, "DATA_REQUEST_UPDATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"entity": entity.name, "status": row.status}, level=1, request=request)
    return serialize_request(row, entity.name)


@router.post("/data-entities", status_code=201)
async def create_data_entity(payload: DataEntityIn, request: Request, db: Session = Depends(get_db),
                             user: User = Depends(require_role(ANALYSIS_ROLES))):
    from db.models_data_requests import DataEntity

    _check_entity(payload)
    if db.query(DataEntity.id).filter(func.lower(DataEntity.name) == payload.name.lower()).first():
        raise HTTPException(409, "Ya existe una dependencia con ese nombre.")
    row = DataEntity(**payload.model_dump())
    db.add(row)
    db.commit()
    await log_audit(db, "DATA_ENTITY_CREATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"name": row.name}, level=1, request=request)
    return {"id": str(row.id), "name": row.name}


@router.put("/data-entities/{entity_id}")
async def update_data_entity(entity_id: UUID, payload: DataEntityIn, request: Request, db: Session = Depends(get_db),
                             user: User = Depends(require_role(ANALYSIS_ROLES))):
    from db.models_data_requests import DataEntity

    _check_entity(payload)
    row = db.get(DataEntity, entity_id)
    if not row:
        raise HTTPException(404, "La dependencia no existe.")
    clash = db.query(DataEntity.id).filter(func.lower(DataEntity.name) == payload.name.lower(),
                                           DataEntity.id != row.id).first()
    if clash:
        raise HTTPException(409, "Ya existe una dependencia con ese nombre.")
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.commit()
    await log_audit(db, "DATA_ENTITY_UPDATED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"name": row.name, "cadence": row.cadence, "active": row.active}, level=1, request=request)
    return {"id": str(row.id), "name": row.name}


class CouncilSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    session_date: date
    note: Optional[str] = Field(default=None, max_length=500)


@router.get("/calendar")
def get_calendar(db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Calendario operativo: qué toca esta semana y cuándo es el próximo Consejo."""
    from services.operating_calendar import build

    return build(db)


@router.post("/council-sessions", status_code=201)
async def create_council_session(payload: CouncilSessionIn, request: Request, db: Session = Depends(get_db),
                                 user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Fija la fecha exacta de una sesión del Consejo (reemplaza la estimación de ese mes)."""
    from db.models_calendar import CouncilSession
    from services.operating_calendar import COUNCIL

    same_month = db.query(CouncilSession).filter(
        CouncilSession.instance == COUNCIL,
        func.extract("year", CouncilSession.session_date) == payload.session_date.year,
        func.extract("month", CouncilSession.session_date) == payload.session_date.month).first()
    if same_month:
        raise HTTPException(409, f"Ya hay una sesión registrada ese mes ({same_month.session_date:%d/%m/%Y}). Bórrela antes de fijar otra.")
    row = CouncilSession(instance=COUNCIL, session_date=payload.session_date, note=payload.note, created_by=user.username)
    db.add(row)
    db.commit()
    await log_audit(db, "COUNCIL_SESSION_SET", actor_id=str(user.id), module="OBSERVATORY",
                    target={"session_date": payload.session_date.isoformat()}, level=1, request=request)
    return {"id": str(row.id), "session_date": row.session_date.isoformat()}


@router.delete("/council-sessions/{session_id}", status_code=204)
async def delete_council_session(session_id: UUID, request: Request, db: Session = Depends(get_db),
                                 user: User = Depends(require_role(ANALYSIS_ROLES))):
    from db.models_calendar import CouncilSession

    row = db.get(CouncilSession, session_id)
    if not row:
        raise HTTPException(404, "La sesión no existe.")
    day = row.session_date.isoformat()
    db.delete(row)
    db.commit()
    await log_audit(db, "COUNCIL_SESSION_REMOVED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"session_date": day}, level=1, request=request)


@router.get("/anomalies")
def get_anomalies(db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Radar de anomalías (uso interno): cifras que se salen de lo esperado, con sus reglas."""
    from services.anomaly_radar import build_anomalies

    return build_anomalies(db)


@router.get("/territories")
def get_territories(db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Territorios con hechos ubicados, en orden alfabético (no es un ranking)."""
    from services.territory_profile import list_territories

    return list_territories(db)


@router.get("/territories/profile")
async def get_territory_profile(request: Request, name: str = Query(min_length=2, max_length=200),
                                db: Session = Depends(get_db), user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Ficha territorial (uso interno): hechos, comparendos, alertas, Defensoría, compromisos y estudios."""
    from services.territory_profile import build_profile

    profile = build_profile(db, name)
    if not profile:
        raise HTTPException(404, "No hay un barrio, vereda o sector oficial con ese nombre.")
    await log_audit(db, "TERRITORY_PROFILE_VIEWED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"territory": profile["name"]}, level=2, request=request)
    return profile


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
    _check_open_limit(db, payload.status)
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
    if row.status not in OPEN_STUDY_STATUSES:
        _check_open_limit(db, payload.status, exclude_id=row.id)
    if payload.status != "PAUSADO":
        payload.status_note = None
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


class FieldNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: str
    on_date: date
    place: Optional[str] = Field(default=None, max_length=200)
    participants: Optional[str] = Field(default=None, max_length=300)  # roles, no nombres
    summary: str = Field(min_length=10, max_length=5000)


@router.post("/studies/{study_id}/field-notes", status_code=201)
async def add_field_note(study_id: UUID, payload: FieldNoteIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require_role(ANALYSIS_ROLES))):
    """Trabajo de campo del estudio: entrevista, recorrido, grupo focal o reunión."""
    import uuid as _uuid

    if payload.kind not in FIELD_NOTE_KINDS:
        raise HTTPException(422, f"Tipo no válido. Use: {', '.join(FIELD_NOTE_KINDS)}.")
    row = _visible_study(db, study_id, user)
    note = {"id": str(_uuid.uuid4()), **payload.model_dump(mode="json"),
            "by": user.username, "at": datetime.now(timezone.utc).isoformat()}
    row.field_notes = [*(row.field_notes or []), note]  # lista nueva: SQLAlchemy detecta el cambio
    db.commit()
    await log_audit(db, "OBSERVATORY_FIELD_NOTE_ADDED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code, "kind": payload.kind}, level=1, request=request)
    return note


@router.delete("/studies/{study_id}/field-notes/{note_id}", status_code=204)
async def delete_field_note(study_id: UUID, note_id: str, request: Request, db: Session = Depends(get_db),
                            user: User = Depends(require_role(ANALYSIS_ROLES))):
    row = _visible_study(db, study_id, user)
    notes = row.field_notes or []
    remaining = [note for note in notes if note.get("id") != note_id]
    if len(remaining) == len(notes):
        raise HTTPException(404, "La nota no existe.")
    row.field_notes = remaining
    db.commit()
    await log_audit(db, "OBSERVATORY_FIELD_NOTE_REMOVED", actor_id=str(user.id), module="OBSERVATORY",
                    target={"code": row.code}, level=1, request=request)


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
