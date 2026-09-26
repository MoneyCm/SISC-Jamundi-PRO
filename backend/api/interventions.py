"""Decisiones e intervenciones: evidencia conservada, comparación descriptiva."""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy.orm import Session

from api.auth import institutional_access, require_role
from db.models import get_db, User
from db.models_alerts import IntelligenceAlert
from db.models_council import CouncilCommitment
from db.models_hechos_seguridad import IngestionRun
from db.models_interventions import InterventionCase, InterventionRevision
from services import intervention_followup
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import FOLLOWUP_INDICATORS, get_indicator_meta

router = APIRouter()
# Quien sigue alertas y compromisos documenta sus intervenciones (la dirección decide).
analyst_or_admin = require_role(["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"])
NOTE = "Cambio observado entre períodos; esta comparación no demuestra que la intervención lo haya causado."
TRANSITIONS = {
    "BORRADOR": {"BORRADOR", "DECIDIDA"},
    "DECIDIDA": {"DECIDIDA", "EN_EJECUCION"},
    "EN_EJECUCION": {"EN_EJECUCION", "FINALIZADA"},
    "FINALIZADA": {"FINALIZADA"},
    "EVALUADA": set(),
}


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    description: str = Field(min_length=1, max_length=500)
    url: HttpUrl


class CaseDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    problem: str = Field(min_length=1, max_length=4000)
    assessment: str = Field(min_length=1, max_length=4000)
    recommendation: str = Field(default="", max_length=4000)
    decision: str = Field(default="", max_length=4000)
    responsible: str = Field(default="", max_length=500)
    decision_date: date | None = None
    deadline: date | None = None
    intervention: str = Field(default="", max_length=4000)
    started_on: date | None = None
    completed_on: date | None = None
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    status: Literal["BORRADOR", "DECIDIDA", "EN_EJECUCION", "FINALIZADA"] = "BORRADOR"
    # Qué debería cambiar si la intervención funciona (municipal, en hechos). Opcional.
    indicator: str | None = None

    @model_validator(mode="after")
    def validate_stage(self):
        if self.indicator and self.indicator not in FOLLOWUP_INDICATORS:
            raise ValueError("Indicador no disponible para seguimiento.")
        if self.status != "BORRADOR":
            if not all([self.recommendation, self.decision, self.responsible, self.decision_date, self.deadline]):
                raise ValueError("La decisión exige recomendación, decisión, responsable, fecha y plazo.")
        if self.decision_date and self.deadline and self.deadline < self.decision_date:
            raise ValueError("El plazo no puede preceder a la decisión.")
        if self.started_on and (not self.decision_date or self.started_on < self.decision_date):
            raise ValueError("El inicio no puede preceder a la decisión.")
        if self.completed_on and (not self.started_on or self.completed_on < self.started_on):
            raise ValueError("El fin no puede preceder al inicio.")
        if any(d and d > date.today() for d in (self.decision_date, self.started_on, self.completed_on)):
            raise ValueError("Las fechas de actuaciones realizadas no pueden ser futuras.")
        if self.status in {"EN_EJECUCION", "FINALIZADA"} and not all([self.intervention, self.started_on]):
            raise ValueError("La ejecución exige intervención y fecha de inicio.")
        if self.status == "FINALIZADA" and not (self.completed_on and self.evidence):
            raise ValueError("Finalizar exige fecha de fin y evidencia documental.")
        return self


class CreateCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: UUID | None = None
    commitment_code: str | None = Field(default=None, max_length=40)
    document: CaseDocument

    @model_validator(mode="after")
    def one_origin(self):
        if bool(self.alert_id) == bool(self.commitment_code):
            raise ValueError("La intervención nace de una alerta o de un compromiso (uno de los dos).")
        return self


class UpdateCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    document: CaseDocument


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=0)
    source_version_id: UUID
    methodology_version: str = Field(min_length=1, max_length=20)
    before_start: date
    before_end: date
    after_start: date
    after_end: date
    assessment: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def comparable(self):
        if self.before_end < self.before_start or self.after_end < self.after_start:
            raise ValueError("Períodos invertidos.")
        if self.before_end >= self.after_start:
            raise ValueError("Los períodos no pueden solaparse.")
        if self.before_end - self.before_start != self.after_end - self.after_start:
            raise ValueError("Los períodos deben tener igual duración.")
        if self.after_end > date.today():
            raise ValueError("El período posterior todavía no ha terminado.")
        return self


def serialize(row):
    return {"id": str(row.id), "alert_id": str(row.alert_id) if row.alert_id else None,
            "commitment_code": row.commitment_code, "version": row.version,
            "status": row.status, "document": row.document, "created_at": row.created_at}


def commitment_snapshot(item: CouncilCommitment) -> dict:
    return {"code": item.code, "text": item.text, "responsible": item.responsible, "instance": item.instance,
            "origin_act": item.origin_act, "origin_date": item.origin_date.isoformat() if item.origin_date else None,
            "deadline_date": item.deadline_date.isoformat() if item.deadline_date else None,
            "theme": item.theme, "territory": item.territory, "status": item.status}


def load_case(db, case_id, expected_version=None):
    q = db.query(InterventionCase).filter(InterventionCase.id == case_id)
    if expected_version is not None:
        q = q.with_for_update()
    row = q.first()
    if not row:
        raise HTTPException(404, "Expediente no encontrado.")
    if expected_version is not None and row.version != expected_version:
        raise HTTPException(409, "Otro analista modificó el expediente. Recargue antes de guardar.")
    return row


def persist_revision(db, row, user, action):
    db.add(InterventionRevision(case_id=row.id, version=row.version, action=action,
        document=row.document, username=user.username, user_id=str(user.id)))
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/")
def list_cases(alert_id: UUID | None = None, commitment_code: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    if not alert_id and not commitment_code:
        raise HTTPException(422, "Indique la alerta o el compromiso.")
    q = db.query(InterventionCase)
    q = q.filter(InterventionCase.alert_id == alert_id) if alert_id else q.filter(
        InterventionCase.commitment_code == commitment_code.strip().upper())
    return {"items": [serialize(r) for r in q.order_by(InterventionCase.created_at.desc()).all()]}


@router.get("/indicators")
def followup_indicators(user: User = Depends(institutional_access)):
    return [{"code": code, "label": get_indicator_meta(code).get("label", code)} for code in FOLLOWUP_INDICATORS]


@router.get("/by-commitment")
def cases_by_commitment(db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    """Estado de las intervenciones de cada compromiso, para marcarlo en la lista."""
    result: dict = {}
    rows = db.query(InterventionCase.commitment_code, InterventionCase.status).filter(
        InterventionCase.commitment_code.isnot(None)).all()
    for code, status in rows:
        result.setdefault(code, []).append(status)
    return result


@router.post("/", status_code=201)
def create_case(payload: CreateCase, db: Session = Depends(get_db), user: User = Depends(analyst_or_admin)):
    if payload.document.status != "BORRADOR":
        raise HTTPException(422, "El expediente se crea como borrador.")
    doc = payload.document.model_dump(mode="json")
    if payload.alert_id:
        alert = db.query(IntelligenceAlert).filter(IntelligenceAlert.id == payload.alert_id).first()
        if not alert:
            raise HTTPException(404, "Alerta no encontrada.")
        doc["alert_snapshot"] = {"id": str(alert.id), "title": alert.title, "evidence": alert.metrics,
                                 "entity_ref": alert.entity_ref, "review_state": alert.review_state}
        row = InterventionCase(alert_id=alert.id, document=doc, status="BORRADOR", version=0)
    else:
        code = payload.commitment_code.strip().upper()
        item = db.query(CouncilCommitment).filter(CouncilCommitment.code == code).first()
        if not item:
            raise HTTPException(404, "Compromiso no encontrado.")
        doc["commitment_snapshot"] = commitment_snapshot(item)
        row = InterventionCase(commitment_code=item.code, document=doc, status="BORRADOR", version=0)
    db.add(row)
    db.flush()
    return persist_revision(db, row, user, "CREACION")


@router.get("/{case_id}")
def detail(case_id: UUID, db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    row = load_case(db, case_id)
    revisions = db.query(InterventionRevision).filter(InterventionRevision.case_id == case_id).order_by(InterventionRevision.version.asc()).all()
    return {**serialize(row), "revisions": [{"version": r.version, "action": r.action,
        "username": r.username, "created_at": r.created_at, "document": r.document} for r in revisions]}


@router.put("/{case_id}")
def update_case(case_id: UUID, payload: UpdateCase, db: Session = Depends(get_db), user: User = Depends(analyst_or_admin)):
    row = load_case(db, case_id, payload.expected_version)
    if payload.document.status not in TRANSITIONS[row.status]:
        raise HTTPException(422, "Transición inválida o expediente evaluado e inmutable.")
    doc = payload.document.model_dump(mode="json")
    # El origen congelado al crear el expediente no se edita.
    for key in ("alert_snapshot", "commitment_snapshot"):
        if key in row.document:
            doc[key] = row.document[key]
    row.document = doc
    row.status = payload.document.status
    row.version += 1
    return persist_revision(db, row, user, "ACTUALIZACION")


def comparison(db, row, payload):
    if row.status != "FINALIZADA":
        raise HTTPException(422, "Finalice la intervención antes de evaluar.")
    doc = row.document
    if payload.before_end >= date.fromisoformat(doc["started_on"]) or payload.after_start <= date.fromisoformat(doc["completed_on"]):
        raise HTTPException(422, "El período inicial debe preceder al inicio y el posterior seguir al fin de la intervención.")
    indicator = intervention_followup.case_indicator(doc)
    if not indicator:
        raise HTTPException(422, "Elija el indicador municipal a comparar; la comparación no extrapola a barrios.")
    run = db.query(IngestionRun).filter(IngestionRun.id == payload.source_version_id).first()
    if not run or run.status != "COMPLETED" or run.fuente_codigo != "POLICIA_SEMANAL":
        raise HTTPException(422, "Se exige una entrega policial completada.")
    if not run.cobertura_inicio or not run.cobertura_fin or run.cobertura_inicio > payload.before_start or run.cobertura_fin < payload.after_end:
        raise HTTPException(422, "La entrega no declara cobertura completa para ambos períodos.")
    kwargs = dict(indicator=indicator, territory="JAMUNDI", source_version_id=str(run.id), methodology_version=payload.methodology_version)
    try:
        before = calculate_indicator(db, period_start=payload.before_start, period_end=payload.before_end, **kwargs)
        after = calculate_indicator(db, period_start=payload.after_start, period_end=payload.after_end, **kwargs)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    delta = after["value"] - before["value"]
    return {"before": before, "after": after, "difference": delta,
            "variation_pct": round(delta / before["value"] * 100, 2) if before["value"] else None,
            "coverage": "COMPLETA_DECLARADA", "assessment": payload.assessment, "note": NOTE}


@router.get("/{case_id}/followup")
def case_followup(case_id: UUID, db: Session = Depends(get_db), user: User = Depends(institutional_access)):
    """Seguimiento a 30, 60 y 90 días desde el inicio: se calcula al consultar, sobre la entrega vigente."""
    row = load_case(db, case_id)
    return intervention_followup.followup(db, row.document)


@router.post("/{case_id}/evaluate")
def evaluate(case_id: UUID, payload: Evaluation, db: Session = Depends(get_db), user: User = Depends(analyst_or_admin)):
    row = load_case(db, case_id, payload.expected_version)
    result = comparison(db, row, payload)
    row.document = {**row.document, "evaluation": result}
    row.status = "EVALUADA"
    row.version += 1
    return persist_revision(db, row, user, "EVALUACION")
