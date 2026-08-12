import hmac
import json
import os
import time
from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from api.auth import get_optional_user, institutional_access, log_audit, require_role
from core.config import is_strong_secret
from db.models import User
from db.session import get_db
from services.source_center_service import SOURCE_CONNECTORS, SourceCenterService


router = APIRouter()
SOURCE_OPERATION_ROLES = ["SOURCE_UPLOADER", "STEWARD", "ANALYST", "FUNC_ADMIN", "TI_ADMIN"]
HEARTBEAT_STATUSES = {"CURRENT", "UPDATED", "UPDATE_AVAILABLE", "ERROR", "NEEDS_REVIEW"}
HEARTBEAT_QUALITY = {"VALIDATED", "WARNING", "INCOMPLETE", "ERROR"}
GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
GITHUB_OIDC_AUDIENCE = "sisc-source-center"
GITHUB_OIDC_JWKS_URL = f"{GITHUB_OIDC_ISSUER}/.well-known/jwks"
TRUSTED_GITHUB_WORKFLOWS = {
    "SIEDCO_PUBLICO": {
        "repository": "MoneyCm/monitor-siedco",
        "workflow_ref": (
            "MoneyCm/monitor-siedco/.github/workflows/monitor_siedco.yml@refs/heads/main"
        ),
    },
    "OBSERVATORIO_VALLE": {
        "repository": "MoneyCm/monitor-valle",
        "workflow_ref": (
            "MoneyCm/monitor-valle/.github/workflows/extract_jamundi.yml@refs/heads/main"
        ),
    },
    "POLICIA_NACIONAL": {
        "repository": "MoneyCm/monitor-policia",
        "workflow_ref": (
            "MoneyCm/monitor-policia/.github/workflows/monitor.yml@refs/heads/main"
        ),
    },
    "MINDEFENSA": {
        "repository": "MoneyCm/monitor-mindefensa",
        "workflow_ref": (
            "MoneyCm/monitor-mindefensa/.github/workflows/monitor.yml@refs/heads/main"
        ),
    },
}
_GITHUB_JWKS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "keys": []}


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


async def _github_jwks(force_refresh: bool = False) -> List[Dict[str, Any]]:
    if not force_refresh and time.monotonic() < _GITHUB_JWKS_CACHE["expires_at"]:
        return _GITHUB_JWKS_CACHE["keys"]
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(GITHUB_OIDC_JWKS_URL)
            response.raise_for_status()
            keys = response.json().get("keys", [])
    except (httpx.HTTPError, ValueError, AttributeError) as error:
        raise HTTPException(
            status_code=503,
            detail="No fue posible validar temporalmente la identidad del monitor.",
        ) from error
    if not isinstance(keys, list) or not keys:
        raise HTTPException(status_code=503, detail="El proveedor de identidad no entrego claves validas.")
    _GITHUB_JWKS_CACHE.update({"expires_at": time.monotonic() + 3600, "keys": keys})
    return keys


def _validate_github_claims(claims: Dict[str, Any], connector_code: str) -> None:
    trust = TRUSTED_GITHUB_WORKFLOWS.get(connector_code)
    repository = str(claims.get("repository") or "")
    workflow_ref = str(claims.get("workflow_ref") or "")
    if not trust or repository.casefold() != trust["repository"].casefold():
        raise HTTPException(status_code=403, detail="Repositorio de monitor no autorizado.")
    if workflow_ref.casefold() != trust["workflow_ref"].casefold():
        raise HTTPException(status_code=403, detail="Workflow de monitor no autorizado.")
    if claims.get("ref") != "refs/heads/main":
        raise HTTPException(status_code=403, detail="Rama de monitor no autorizada.")
    if claims.get("event_name") not in {"schedule", "workflow_dispatch", "push"}:
        raise HTTPException(status_code=403, detail="Evento de monitor no autorizado.")
    if claims.get("runner_environment") != "github-hosted":
        raise HTTPException(status_code=403, detail="Entorno de monitor no autorizado.")


async def _authorize_github_oidc(token: str, connector_code: str) -> str:
    if not token or len(token) > 20_000:
        raise HTTPException(status_code=403, detail="Identidad de monitor no valida.")
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as error:
        raise HTTPException(status_code=403, detail="Identidad de monitor no valida.") from error
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise HTTPException(status_code=403, detail="Identidad de monitor no valida.")

    keys = await _github_jwks()
    key = next((item for item in keys if item.get("kid") == header["kid"]), None)
    if key is None:
        keys = await _github_jwks(force_refresh=True)
        key = next((item for item in keys if item.get("kid") == header["kid"]), None)
    if key is None:
        raise HTTPException(status_code=403, detail="Clave de identidad no reconocida.")
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=GITHUB_OIDC_AUDIENCE,
            issuer=GITHUB_OIDC_ISSUER,
        )
    except JWTError as error:
        raise HTTPException(status_code=403, detail="Identidad de monitor no valida.") from error
    _validate_github_claims(claims, connector_code)
    return "GITHUB_OIDC"


async def _authorize_heartbeat(
    request: Request,
    user: Optional[User],
    connector_code: Optional[str] = None,
) -> str:
    role_codes = {role.code for role in (user.roles or [])} if user else set()
    if role_codes.intersection(SOURCE_OPERATION_ROLES):
        return "USER"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and connector_code:
        return await _authorize_github_oidc(auth_header.split(" ", 1)[1], connector_code)

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
    mode = await _authorize_heartbeat(request, current_user, code)
    # Un error reciente no debe borrar el ultimo corte o exito conocido.
    data = payload.model_dump(exclude_none=True)
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
    raise HTTPException(
        status_code=409,
        detail=(
            "Esta fuente se revisa mediante su monitor externo. "
            "El Centro de fuentes recibe el estado automaticamente."
        ),
    )
