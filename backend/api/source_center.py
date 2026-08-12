import hmac
import json
import os
from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from api.auth import get_optional_user, institutional_access, log_audit, require_role
from core.config import is_strong_secret
from db.models import User
from db.session import get_db
from services.mindefensa_monitor import MindefensaMonitorService
from services.policia_monitor import PoliceMonitorService
from services.source_center_service import SOURCE_CONNECTORS, SourceCenterService


router = APIRouter()
SOURCE_OPERATION_ROLES = ["SOURCE_UPLOADER", "STEWARD", "ANALYST", "FUNC_ADMIN", "TI_ADMIN"]
HEARTBEAT_STATUSES = {"CURRENT", "UPDATED", "UPDATE_AVAILABLE", "ERROR", "NEEDS_REVIEW"}
HEARTBEAT_QUALITY = {"VALIDATED", "WARNING", "INCOMPLETE", "ERROR"}


WarningText = Annotated[str, Field(max_length=500)]


class SourceHeartbeat(BaseModel):
    connector_code: str = Field(min_length=3, max_length=50)
    status: str = Field(default="CURRENT", max_length=40)
    quality_status: str = Field(default="VALIDATED", max_length=40)
    period_label: Optional[str] = Field(default=None, max_length=160)
    source_cutoff_date: Optional[date] = None
    last_checked_at: datetime
    last_success_at: Optional[datetime] = None
    last_change_detected_at: Optional[datetime] = None
    record_count: Optional[int] = Field(default=None, ge=0)
    indicator_count: Optional[int] = Field(default=None, ge=0)
    warnings: List[WarningText] = Field(default_factory=list, max_length=30)
    details: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def validate_details_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=True, default=str)) > 20_000:
            raise ValueError("El detalle del monitor supera el tamano permitido.")
        return value


def _authorize_heartbeat(request: Request, user: Optional[User]) -> str:
    role_codes = {role.code for role in (user.roles or [])} if user else set()
    if role_codes.intersection(SOURCE_OPERATION_ROLES):
        return "USER"
    expected_key = os.getenv("SISC_SOURCE_MONITOR_KEY", "").strip()
    if not is_strong_secret(expected_key):
        raise HTTPException(status_code=503, detail="La integracion de monitores no esta configurada.")
    provided_key = request.headers.get("X-SISC-SOURCE-KEY", "")
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(status_code=403, detail="Acceso denegado.")
    return "SERVICE"


@router.get("")
def get_source_center(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    return SourceCenterService.summary(db)


@router.post("/heartbeat")
async def source_heartbeat(
    payload: SourceHeartbeat,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    code = payload.connector_code.strip().upper()
    if code not in SOURCE_CONNECTORS:
        raise HTTPException(status_code=404, detail="Conector de fuente no registrado.")
    status = payload.status.strip().upper()
    quality = payload.quality_status.strip().upper()
    if status not in HEARTBEAT_STATUSES or quality not in HEARTBEAT_QUALITY:
        raise HTTPException(status_code=422, detail="Estado o calidad no permitidos.")
    mode = _authorize_heartbeat(request, current_user)
    data = payload.model_dump()
    data.update({"status": status, "quality_status": quality})
    SourceCenterService.record_heartbeat(db, code, data)
    await log_audit(
        db,
        "SOURCE_MONITOR_HEARTBEAT",
        actor_id=str(current_user.id) if current_user else None,
        module="SOURCE_CENTER",
        target={"connector_code": code, "status": status, "mode": mode},
        level=2,
        request=request,
    )
    return {"accepted": True, "connector_code": code, "status": status}


@router.post("/check/{connector_code}")
async def check_source_connector(
    connector_code: str,
    request: Request,
    dataset_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(SOURCE_OPERATION_ROLES)),
):
    code = connector_code.strip().upper()
    if code == "MINDEFENSA":
        from db.models_mindefensa import MindefensaAsset

        if db.query(MindefensaAsset).count() == 0:
            MindefensaMonitorService.seed_initial_assets(db)
        if dataset_code:
            asset = db.query(MindefensaAsset).filter_by(dataset_code=dataset_code.strip()).first()
            if asset is None:
                raise HTTPException(status_code=404, detail="Archivo de fuente no registrado.")
            result = await MindefensaMonitorService.check_asset(db, asset)
        else:
            result = await MindefensaMonitorService.check_all_assets(db)
    elif code == "POLICIA_NACIONAL":
        from db.models_policia import PoliceAsset

        if db.query(PoliceAsset).count() == 0:
            PoliceMonitorService.seed_initial_assets(db)
        if dataset_code:
            asset = db.query(PoliceAsset).filter_by(dataset_code=dataset_code.strip()).first()
            if asset is None:
                raise HTTPException(status_code=404, detail="Archivo de fuente no registrado.")
            result = await PoliceMonitorService.check_asset(db, asset)
        else:
            result = await PoliceMonitorService.check_all_assets(db)
    else:
        raise HTTPException(
            status_code=409,
            detail="Esta fuente se actualiza mediante su monitor externo o una carga institucional.",
        )
    await log_audit(
        db,
        "SOURCE_CONNECTOR_CHECKED",
        actor_id=str(current_user.id),
        module="SOURCE_CENTER",
        target={"connector_code": code, "dataset_code": dataset_code, "result": result},
        level=2,
        request=request,
    )
    return {"result": result, "summary": SourceCenterService.summary(db)}
