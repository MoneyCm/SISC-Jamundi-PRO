from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime

from core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM
from db.models import get_db, User, Role
from db.models_auth import AuditLog
from db.schemas import Token, TokenData

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# Helper para auditoría
async def log_audit(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    module: Optional[str] = None,
    target: Optional[dict] = None,
    level: int = 1,
    request: Request = None
):
    ip = request.client.host if request else None
    ua = request.headers.get("user-agent") if request else None
    
    log = AuditLog(
        actor_user_id=actor_id,
        action=action,
        module=module,
        target_ref=target,
        data_level=level,
        ip=ip,
        user_agent=ua
    )
    db.add(log)
    db.commit()

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        roles: List[str] = payload.get("roles", [])
        data_level: int = payload.get("dl", 1)
        
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, roles=roles, data_level_max=data_level)
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    
    # Verificar expiración de cuenta (para N3)
    if user.expires_at and user.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su cuenta ha expirado. Contacte al administrador."
        )
        
    return user

async def get_optional_user(
    db: Session = Depends(get_db),
    request: Request = None
) -> Optional[User]:
    """Tries to get the user from the Authorization header or token query param."""
    if not request:
        return None
        
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")
        
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            return None
        
        user = db.query(User).filter(User.username == username).first()
        if user and user.is_active:
            # Check expiration for N3 users
            if user.expires_at and user.expires_at < datetime.utcnow():
                return None
            return user
    except JWTError:
        pass
    return None

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        await log_audit(db, "LOGIN_FAILED", target={"username": form_data.username}, request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    # Extraer códigos de roles
    role_codes = [r.code for r in user.roles]
    
    # Actualizar last_login
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Auditoría
    await log_audit(db, "LOGIN", actor_id=str(user.id), request=request)
    
    access_token = create_access_token(
        data={
            "sub": user.username,
            "roles": role_codes,
            "dl": user.data_level_max
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "roles": [r.code for r in current_user.roles],
        "data_level_max": current_user.data_level_max,
        "dependency": current_user.dependency,
        "is_active": current_user.is_active
    }

# --- LÓGICA DE RBAC Y NIVELES DE DATO ---

class SecurityChecker:
    def __init__(self, allowed_roles: List[str] = None, min_data_level: int = 1):
        self.allowed_roles = allowed_roles
        self.min_data_level = min_data_level

    def __call__(self, current_user: User = Depends(get_current_user)):
        # TI_ADMIN siempre pasa si el nivel de dato lo permite
        user_role_codes = [r.code for r in current_user.roles]
        
        # 1. Verificar Nivel de Dato
        if current_user.data_level_max < self.min_data_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere nivel de datos {self.min_data_level} (Usted: {current_user.data_level_max})"
            )

        # 2. Verificar Roles (si se especifican)
        if self.allowed_roles:
            # TI_ADMIN es superuser para gestión
            if "TI_ADMIN" in user_role_codes:
                return current_user
                
            has_role = any(role in user_role_codes for role in self.allowed_roles)
            if not has_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. Se requiere uno de los siguientes roles: {', '.join(self.allowed_roles)}"
                )
        
        return current_user

# Dependencias predefinidas
def require_role(roles: List[str]):
    return SecurityChecker(allowed_roles=roles)

def require_data_level(level: int):
    return SecurityChecker(min_data_level=level)

# Roles comunes
is_admin = SecurityChecker(allowed_roles=["TI_ADMIN", "FUNC_ADMIN"])
is_data_owner = SecurityChecker(allowed_roles=["DATA_OWNER"])
institutional_access = SecurityChecker(min_data_level=2)
restricted_access = SecurityChecker(min_data_level=3)
