"""Alertas Narrativas: generar, revisar, editar y marcar como enviados los mensajes para WhatsApp."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.auth import institutional_access, log_audit, require_role
from db.models import User, get_db
from db.models_narrative_alerts import NarrativeAlert, NarrativeAlertRevision
from services import narrative_alerts as service

router = APIRouter()

# Mismo equipo que lleva el seguimiento de los compromisos del Consejo.
EDITOR_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]
FREQUENCY_PATTERN = "^(" + "|".join(service.TYPES) + ")$"


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: str = Field(pattern=FREQUENCY_PATTERN)


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=max(service.max_chars(code) for code in service.TYPES) * 2)
    expected_version: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class StateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=300)


def _errors(call):
    try:
        return call()
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/rules")
def rules(current_user: User = Depends(institutional_access)):
    return {"rules_version": service.RULES_VERSION, "rules": service.RULES,
            "types": [{"code": code, "label": config["label"], "title": config["title"],
                       "max_lines": config["max_lines"], "max_chars": service.max_chars(code)}
                      for code, config in service.TYPES.items()]}


@router.get("/")
def list_alerts(
    frequency: Optional[str] = Query(default=None, pattern=FREQUENCY_PATTERN),
    status: Optional[str] = Query(default=None, pattern="^(BORRADOR|ENVIADO|DESCARTADO|REEMPLAZADO)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    query = db.query(NarrativeAlert)
    if frequency:
        query = query.filter(NarrativeAlert.frequency == frequency)
    if status:
        query = query.filter(NarrativeAlert.status == status)
    rows = query.order_by(NarrativeAlert.created_at.desc()).limit(limit).all()
    return [service.serialize(row) for row in rows]


@router.get("/preview")
def preview(frequency: str = Query(pattern=FREQUENCY_PATTERN), db: Session = Depends(get_db),
            current_user: User = Depends(institutional_access)):
    """Calcula el mensaje sin guardarlo."""
    data = _errors(lambda: service.compute(db, frequency))
    return {"frequency": frequency, "text": data["text"], "data_cutoff": data["cutoff"].isoformat(),
            "source_version_id": data["source_version_id"], "evidence": data["evidence"]}


@router.post("/generate")
async def generate(payload: GenerateRequest, request: Request, db: Session = Depends(get_db),
                   current_user: User = Depends(require_role(EDITOR_ROLES))):
    alert, created = _errors(lambda: service.generate(db, payload.frequency, current_user.username))
    if created:
        await log_audit(db, "NARRATIVE_ALERT_GENERATED", actor_id=str(current_user.id), module="NARRATIVE_ALERTS",
                        target={"id": str(alert.id), "frequency": alert.frequency,
                                "period_end": alert.period_end.isoformat()}, level=1, request=request)
    return {**service.serialize(alert), "created": created}


@router.get("/{alert_id}")
def detail(alert_id: str, db: Session = Depends(get_db), current_user: User = Depends(institutional_access)):
    alert = _errors(lambda: service._get(db, alert_id))
    revisions = (db.query(NarrativeAlertRevision).filter(NarrativeAlertRevision.alert_id == alert.id)
                 .order_by(NarrativeAlertRevision.version.asc(), NarrativeAlertRevision.created_at.asc()).all())
    return service.serialize(alert, revisions)


async def _audited(db, request, current_user, action, alert):
    await log_audit(db, action, actor_id=str(current_user.id), module="NARRATIVE_ALERTS",
                    target={"id": str(alert.id), "version": alert.version, "status": alert.status},
                    level=1, request=request)
    return service.serialize(alert)


@router.put("/{alert_id}/text")
async def edit_text(alert_id: str, payload: EditRequest, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(EDITOR_ROLES))):
    alert = _errors(lambda: service.edit(db, alert_id, payload.text, payload.expected_version,
                                         current_user.username, payload.note))
    return await _audited(db, request, current_user, "NARRATIVE_ALERT_EDITED", alert)


@router.post("/{alert_id}/sent")
async def mark_sent(alert_id: str, payload: StateRequest, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(EDITOR_ROLES))):
    alert = _errors(lambda: service.mark_sent(db, alert_id, payload.expected_version, current_user.username,
                                              payload.note))
    return await _audited(db, request, current_user, "NARRATIVE_ALERT_SENT", alert)


@router.post("/{alert_id}/refresh")
async def refresh(alert_id: str, payload: StateRequest, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_role(EDITOR_ROLES))):
    """Recalcula un borrador con la última sábana y el estado actual de los compromisos."""
    alert = _errors(lambda: service.refresh(db, alert_id, payload.expected_version, current_user.username))
    return await _audited(db, request, current_user, "NARRATIVE_ALERT_REFRESHED", alert)


@router.post("/{alert_id}/discard")
async def discard(alert_id: str, payload: StateRequest, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_role(EDITOR_ROLES))):
    alert = _errors(lambda: service.discard(db, alert_id, payload.expected_version, current_user.username,
                                            payload.note or ""))
    return await _audited(db, request, current_user, "NARRATIVE_ALERT_DISCARDED", alert)
