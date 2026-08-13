import re
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.security import get_password_hash, verify_password
from db.models import Role, User, get_db
from db.models_auth import AccessRequest, AuditLog
from db.schemas import (
    AccessRequest as ARSchema,
    AccessRequestCreate,
    AdminPasswordReset,
    PasswordChange,
    User as UserSchema,
    UserCreate,
    UserStatusUpdate,
    UserUpdate,
)
from .auth import get_current_user, log_audit, require_role

router = APIRouter()

ROLE_MIN_DATA_LEVEL = {
    "TI_ADMIN": 3,
    "FUNC_ADMIN": 2,
    "DATA_OWNER": 3,
    "STEWARD": 2,
    "ANALYST": 2,
    "DIRECTIVE": 2,
    "SOURCE_UPLOADER": 2,
    "PORTAL_EDITOR": 1,
    "PORTAL_ADMIN": 2,
}
REQUESTABLE_ROLE_CODES = {
    "STEWARD",
    "ANALYST",
    "DIRECTIVE",
    "SOURCE_UPLOADER",
    "PORTAL_EDITOR",
}


def _actor_roles(user: User) -> set[str]:
    return {role.code for role in (user.roles or [])}


def _validate_password_strength(password: str, username: str = "") -> None:
    checks = (
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    )
    if len(password) < 12 or sum(checks) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 12 caracteres y combinar mayúsculas, minúsculas, números o símbolos.",
        )
    if username and username.lower() in password.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no puede contener el nombre de usuario.",
        )


def _resolve_roles(
    db: Session,
    role_codes: List[str],
    data_level: int,
    *,
    requestable_only: bool = False,
) -> List[Role]:
    normalized = sorted({str(code).strip().upper() for code in role_codes if str(code).strip()})
    if requestable_only:
        forbidden = sorted(set(normalized) - REQUESTABLE_ROLE_CODES)
        if forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Estos roles no pueden solicitarse por autoservicio: {', '.join(forbidden)}.",
            )

    roles = db.query(Role).filter(Role.code.in_(normalized)).all() if normalized else []
    found = {role.code for role in roles}
    unknown = sorted(set(normalized) - found)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roles desconocidos: {', '.join(unknown)}.",
        )

    incompatible = [
        code for code in normalized
        if ROLE_MIN_DATA_LEVEL.get(code, 1) > data_level
    ]
    if incompatible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nivel N{data_level} es insuficiente para: {', '.join(incompatible)}.",
        )
    return roles


def _is_last_active_ti_admin(db: Session, user: User) -> bool:
    if "TI_ADMIN" not in _actor_roles(user) or not user.is_active:
        return False
    active_admins = db.query(User).filter(
        User.is_active.is_(True),
        User.roles.any(Role.code == "TI_ADMIN"),
    ).count()
    return active_admins <= 1


def _touch_user(user: User) -> None:
    user.updated_at = datetime.utcnow()


@router.get("/", response_model=List[UserSchema])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN", "FUNC_ADMIN"])),
):
    return db.query(User).order_by(User.is_active.desc(), User.full_name, User.username).all()


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"])),
):
    username = user_in.username.strip().lower()
    email = str(user_in.email).strip().lower()
    _validate_password_strength(user_in.password, username)

    if db.query(User).filter(func.lower(User.username) == username).first():
        raise HTTPException(status_code=409, detail="El nombre de usuario ya existe.")
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=409, detail="El correo institucional ya existe.")

    roles = _resolve_roles(db, user_in.role_codes, user_in.data_level_max)
    new_user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip() if user_in.full_name else None,
        dependency=user_in.dependency.strip() if user_in.dependency else None,
        position=user_in.position.strip() if user_in.position else None,
        data_level_max=user_in.data_level_max,
        is_active=user_in.is_active,
        roles=roles,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    await log_audit(
        db,
        "USER_CREATE",
        actor_id=str(current_user.id),
        module="users",
        target={"user_id": str(new_user.id), "roles": [role.code for role in roles]},
        level=new_user.data_level_max,
        request=request,
    )
    return new_user


@router.patch("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"])),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    changes = user_in.model_dump(exclude_unset=True)
    role_codes = changes.pop("role_codes", None)
    requested_level = changes.get("data_level_max", user.data_level_max)

    if "email" in changes and changes["email"] is not None:
        email = str(changes["email"]).strip().lower()
        duplicate = db.query(User).filter(
            func.lower(User.email) == email,
            User.id != user.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="El correo institucional ya existe.")
        changes["email"] = email

    next_roles = user.roles
    if role_codes is not None:
        next_roles = _resolve_roles(db, role_codes, requested_level)
        next_role_codes = {role.code for role in next_roles}
        if user.id == current_user.id and "TI_ADMIN" not in next_role_codes:
            raise HTTPException(status_code=400, detail="No puede retirar su propio rol TI_ADMIN.")
        if "TI_ADMIN" not in next_role_codes and _is_last_active_ti_admin(db, user):
            raise HTTPException(status_code=400, detail="Debe permanecer al menos un administrador TI activo.")
    else:
        _resolve_roles(db, [role.code for role in user.roles], requested_level)

    if changes.get("is_active") is False:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta.")
        if _is_last_active_ti_admin(db, user):
            raise HTTPException(status_code=400, detail="Debe permanecer al menos un administrador TI activo.")

    for field, value in changes.items():
        if field in {"full_name", "dependency", "position"} and isinstance(value, str):
            value = value.strip() or None
        setattr(user, field, value)
    if role_codes is not None:
        user.roles = next_roles
    _touch_user(user)
    db.commit()
    db.refresh(user)

    await log_audit(
        db,
        "USER_UPDATE",
        actor_id=str(current_user.id),
        module="users",
        target={"user_id": str(user.id), "fields": sorted(changes.keys() | ({"roles"} if role_codes is not None else set()))},
        level=user.data_level_max,
        request=request,
    )
    return user


@router.post("/{user_id}/status", response_model=UserSchema)
async def set_user_status(
    user_id: UUID,
    status_in: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"])),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if not status_in.is_active:
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta.")
        if _is_last_active_ti_admin(db, user):
            raise HTTPException(status_code=400, detail="Debe permanecer al menos un administrador TI activo.")

    user.is_active = status_in.is_active
    _touch_user(user)
    db.commit()
    db.refresh(user)
    await log_audit(
        db,
        "USER_ENABLE" if user.is_active else "USER_DISABLE",
        actor_id=str(current_user.id),
        module="users",
        target={"user_id": str(user.id)},
        level=user.data_level_max,
        request=request,
    )
    return user


@router.post("/{user_id}/disable", response_model=UserSchema, deprecated=True)
async def disable_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"])),
):
    return await set_user_status(
        user_id,
        UserStatusUpdate(is_active=False),
        request,
        db,
        current_user,
    )


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    reset_in: AdminPasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"])),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    _validate_password_strength(reset_in.temporary_password, user.username)
    user.password_hash = get_password_hash(reset_in.temporary_password)
    _touch_user(user)
    db.commit()
    await log_audit(
        db,
        "PASSWORD_RESET",
        actor_id=str(current_user.id),
        module="users",
        target={"user_id": str(user.id)},
        level=user.data_level_max,
        request=request,
    )
    return {"status": "success", "message": "Contraseña temporal actualizada; las sesiones anteriores quedaron invalidadas."}


@router.post("/me/password")
async def change_own_password(
    password_in: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(password_in.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    if verify_password(password_in.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente.")
    _validate_password_strength(password_in.new_password, current_user.username)
    current_user.password_hash = get_password_hash(password_in.new_password)
    _touch_user(current_user)
    db.commit()
    await log_audit(
        db,
        "PASSWORD_CHANGE",
        actor_id=str(current_user.id),
        module="users",
        target={"user_id": str(current_user.id)},
        level=current_user.data_level_max,
        request=request,
    )
    return {"status": "success", "message": "Contraseña actualizada; debe iniciar sesión nuevamente."}


@router.post("/access-requests", response_model=ARSchema)
async def create_access_request(
    ar_in: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    roles = _resolve_roles(
        db,
        ar_in.requested_roles,
        ar_in.requested_data_level,
        requestable_only=True,
    )
    requested_codes = [role.code for role in roles]
    current_codes = _actor_roles(current_user)
    if ar_in.requested_data_level <= current_user.data_level_max and set(requested_codes).issubset(current_codes):
        raise HTTPException(status_code=400, detail="La cuenta ya dispone del acceso solicitado.")
    if ar_in.requested_data_level == 3 and not ar_in.duration_days:
        raise HTTPException(status_code=400, detail="El acceso N3 debe tener una vigencia definida.")

    duplicate = db.query(AccessRequest).filter(
        AccessRequest.user_id == current_user.id,
        AccessRequest.status == "PENDING",
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe una solicitud de acceso pendiente.")

    new_request = AccessRequest(
        user_id=current_user.id,
        requested_roles=requested_codes,
        requested_data_level=ar_in.requested_data_level,
        justification=ar_in.justification.strip(),
        duration_days=ar_in.duration_days,
        status="PENDING",
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


@router.get("/access-requests/pending", response_model=List[ARSchema])
async def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["FUNC_ADMIN", "DATA_OWNER"])),
):
    query = db.query(AccessRequest).filter(AccessRequest.status == "PENDING")
    user_roles = _actor_roles(current_user)
    if "DATA_OWNER" in user_roles and "FUNC_ADMIN" not in user_roles and "TI_ADMIN" not in user_roles:
        query = query.filter(AccessRequest.requested_data_level == 3)
    return query.order_by(AccessRequest.created_at.asc()).all()


@router.post("/access-requests/{request_id}/approve")
async def approve_request(
    request_id: UUID,
    req_meta: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["FUNC_ADMIN", "DATA_OWNER"])),
):
    access_req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not access_req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if access_req.status != "PENDING":
        raise HTTPException(status_code=409, detail="La solicitud ya fue decidida.")
    if access_req.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="No puede aprobar su propia solicitud.")

    requested_roles = _resolve_roles(
        db,
        access_req.requested_roles or [],
        access_req.requested_data_level,
        requestable_only=True,
    )
    approver_roles = _actor_roles(current_user)

    if access_req.requested_data_level == 3:
        can_approve_functionally = "FUNC_ADMIN" in approver_roles or "TI_ADMIN" in approver_roles
        can_approve_as_owner = "DATA_OWNER" in approver_roles
        if not access_req.approved_by_func_admin and can_approve_functionally:
            access_req.approved_by_func_admin = current_user.id
        elif not access_req.approved_by_data_owner and can_approve_as_owner:
            if access_req.approved_by_func_admin == current_user.id:
                raise HTTPException(status_code=403, detail="El acceso N3 requiere dos aprobadores diferentes.")
            access_req.approved_by_data_owner = current_user.id
        else:
            raise HTTPException(status_code=409, detail="La aprobación que puede emitir ya fue registrada.")

        if (
            access_req.approved_by_func_admin
            and access_req.approved_by_data_owner
            and access_req.approved_by_func_admin == access_req.approved_by_data_owner
        ):
            raise HTTPException(status_code=403, detail="El acceso N3 requiere dos aprobadores diferentes.")
        fully_approved = bool(access_req.approved_by_func_admin and access_req.approved_by_data_owner)
    else:
        if "FUNC_ADMIN" not in approver_roles and "TI_ADMIN" not in approver_roles:
            raise HTTPException(status_code=403, detail="Solo la administración funcional puede aprobar N1/N2.")
        access_req.approved_by_func_admin = current_user.id
        fully_approved = True

    if fully_approved:
        user = db.query(User).filter(User.id == access_req.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=409, detail="La cuenta solicitante no está activa.")
        access_req.status = "APPROVED"
        access_req.decided_at = datetime.utcnow()
        user.data_level_max = max(user.data_level_max, access_req.requested_data_level)
        for role in requested_roles:
            if role not in user.roles:
                user.roles.append(role)
        if access_req.requested_data_level == 3 and access_req.duration_days:
            user.expires_at = datetime.utcnow() + timedelta(days=access_req.duration_days)
        _touch_user(user)

    db.commit()
    await log_audit(
        db,
        "ACCESS_APPROVE",
        actor_id=str(current_user.id),
        module="users",
        target={"request_id": str(request_id), "user_id": str(access_req.user_id), "status": access_req.status},
        request=req_meta,
    )
    return {"status": access_req.status}


@router.post("/access-requests/{request_id}/reject")
async def reject_request(
    request_id: UUID,
    req_meta: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["FUNC_ADMIN", "DATA_OWNER"])),
):
    access_req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not access_req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if access_req.status != "PENDING":
        raise HTTPException(status_code=409, detail="La solicitud ya fue decidida.")
    if access_req.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="No puede decidir su propia solicitud.")
    access_req.status = "REJECTED"
    access_req.decided_at = datetime.utcnow()
    db.commit()
    await log_audit(
        db,
        "ACCESS_REJECT",
        actor_id=str(current_user.id),
        module="users",
        target={"request_id": str(request_id), "user_id": str(access_req.user_id)},
        request=req_meta,
    )
    return {"status": "REJECTED"}


@router.get("/audit", response_model=List[dict])
async def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN", "FUNC_ADMIN"])),
):
    safe_limit = min(max(limit, 1), 500)
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(safe_limit).all()
    return [
        {
            "id": item.id,
            "actor": str(item.actor_user_id) if item.actor_user_id else None,
            "action": item.action,
            "module": item.module,
            "target": item.target_ref,
            "level": item.data_level,
            "ip": item.ip,
            "user_agent": item.user_agent,
            "created_at": item.created_at,
        }
        for item in logs
    ]
