from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from db.models import get_db, User, Role
from db.models_auth import Permission, AccessRequest, AuditLog, UserRole, role_permissions
from db.schemas import User as UserSchema, UserCreate, UserUpdate, AccessRequest as ARSchema, AccessRequestCreate
from .auth import get_current_user, require_role, is_admin, log_audit

router = APIRouter()

# --- USERS ---

@router.get("/", response_model=List[UserSchema])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN", "FUNC_ADMIN"]))
):
    return db.query(User).all()

@router.post("/", response_model=UserSchema, status_code=201)
async def create_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(require_role(["TI_ADMIN"])),
):
    from core.security import get_password_hash
    
    # Validar duplicados
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        dependency=user_in.dependency,
        position=user_in.position,
        data_level_max=user_in.data_level_max,
        is_active=user_in.is_active
    )
    db.add(new_user)
    db.flush() # Para tener el ID
    
    # Asignar roles iniciales
    if user_in.role_codes:
        roles = db.query(Role).filter(Role.code.in_(user_in.role_codes)).all()
        new_user.roles = roles
    
    db.commit()
    db.refresh(new_user)
    
    await log_audit(db, "USER_CREATE", actor_id=str(db.query(User).filter(User.username == "admin").first().id if not current_user else current_user.id), 
                    target={"user_id": str(new_user.id)}, request=request)
    
    return new_user

@router.post("/{user_id}/disable")
async def disable_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    await log_audit(db, "USER_DISABLE", actor_id=str(current_user.id), target={"user_id": str(user_id)}, request=request)
    return {"status": "success"}

# --- ACCESS REQUESTS ---

@router.post("/access-requests", response_model=ARSchema)
async def create_access_request(
    ar_in: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_request = AccessRequest(
        user_id=current_user.id,
        requested_roles=ar_in.requested_roles,
        requested_data_level=ar_in.requested_data_level,
        justification=ar_in.justification,
        duration_days=ar_in.duration_days,
        status="PENDING"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request

@router.get("/access-requests/pending", response_model=List[ARSchema])
async def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["FUNC_ADMIN", "DATA_OWNER"]))
):
    query = db.query(AccessRequest).filter(AccessRequest.status == "PENDING")
    
    # Filtro: DATA_OWNER solo ve N3
    user_roles = [r.code for r in current_user.roles]
    if "DATA_OWNER" in user_roles and "FUNC_ADMIN" not in user_roles:
        query = query.filter(AccessRequest.requested_data_level == 3)
        
    return query.all()

@router.post("/access-requests/{request_id}/approve")
async def approve_request(
    request_id: UUID,
    req_meta: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["FUNC_ADMIN", "DATA_OWNER"]))
):
    access_req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not access_req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    user_roles = [r.code for r in current_user.roles]
    
    # Lógica de doble aprobación para N3
    if access_req.requested_data_level == 3:
        if "DATA_OWNER" not in user_roles:
            raise HTTPException(status_code=403, detail="Solo un DATA_OWNER puede aprobar nivel N3")
        access_req.approved_by_data_owner = current_user.id
    else:
        access_req.approved_by_func_admin = current_user.id

    # Si ya tiene las aprobaciones necesarias (N1/N2 solo FUNC_ADMIN, N3 requiere DATA_OWNER)
    # Nota: simplificamos a que FUNC_ADMIN aprueba N1/N2 solo, y N3 necesita DATA_OWNER.
    is_fully_approved = False
    if access_req.requested_data_level < 3 and access_req.approved_by_func_admin:
        is_fully_approved = True
    elif access_req.requested_data_level == 3 and access_req.approved_by_data_owner:
        is_fully_approved = True
        
    if is_fully_approved:
        access_req.status = "APPROVED"
        access_req.decided_at = datetime.utcnow()
        
        # Aplicar cambios al usuario
        user = db.query(User).filter(User.id == access_req.user_id).first()
        if user:
            if access_req.requested_data_level > user.data_level_max:
                user.data_level_max = access_req.requested_data_level
            
            # Asignar roles
            if access_req.requested_roles:
                roles = db.query(Role).filter(Role.code.in_(access_req.requested_roles)).all()
                for r in roles:
                    if r not in user.roles:
                        user.roles.append(r)
            
            if access_req.requested_data_level == 3 and access_req.duration_days:
                user.expires_at = datetime.utcnow() + timedelta(days=access_req.duration_days)
    
    db.commit()
    await log_audit(db, "ACCESS_APPROVE", actor_id=str(current_user.id), 
                    target={"request_id": str(request_id), "user_id": str(access_req.user_id)}, request=req_meta)
    
    return {"status": access_req.status}

# --- AUDIT ---

@router.get("/audit", response_model=List[dict])
async def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN", "FUNC_ADMIN"]))
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    # Manual serialization to avoid issues with JSONB/UUID in standard response_model if not configured
    return [{
        "id": l.id,
        "actor": str(l.actor_user_id),
        "action": l.action,
        "module": l.module,
        "target": l.target_ref,
        "level": l.data_level,
        "ip": l.ip,
        "user_agent": l.user_agent,
        "created_at": l.created_at
    } for l in logs]
