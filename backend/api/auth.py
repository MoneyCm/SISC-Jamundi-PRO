# backend/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from datetime import datetime
from typing import List, Optional

from core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM
from db.models import get_db, User  # Role es opcional si lo usas en otro lado
from db.models_auth import AuditLog
from db.schemas import Token, TokenData

router = APIRouter()

# OJO: tokenUrl debe coincidir con la ruta real del login en tu app.
# Como este router se monta en main.py con prefix="/api/auth", tokenUrl debe ser "api/auth/login"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


# ----------------------------
# Auditoría
# ----------------------------
async def log_audit(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    module: Optional[str] = None,
    target: Optional[dict] = None,
    level: int = 1,
    request: Optional[Request] = None,
):
    try:
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None

        log = AuditLog(
            actor_user_id=actor_id,
            action=action,
            module=module,
            target_ref=target,
            data_level=level,
            ip=ip,
            user_agent=ua,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"⚠️ Error de auditoría (no crítico): {e}")
        db.rollback()


# ----------------------------
# Auth helpers
# ----------------------------
async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        roles: List[str] = payload.get("roles", [])
        data_level: int = payload.get("dl", 1)

        if not username:
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
            detail="Su cuenta ha expirado. Contacte al administrador.",
        )

    return user


async def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Intenta obtener el usuario desde:
    - Authorization: Bearer <token>
    - ?token=<token> (para descargas tokenizadas si las usas)
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        token = request.query_params.get("token")

    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            return None

        user = db.query(User).filter(User.username == username).first()
        if user and user.is_active:
            if user.expires_at and user.expires_at < datetime.utcnow():
                return None
            return user
    except JWTError:
        return None

    return None


# ----------------------------
# Endpoints
# ----------------------------
@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")

    # Extraer códigos de roles
    role_codes = [r.code for r in (user.roles or [])]

    # Actualizar last_login
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Auditoría
    await log_audit(db, "LOGIN", actor_id=str(user.id), module="auth", request=request)

    access_token = create_access_token(
        data={
            "sub": user.username,
            "roles": role_codes,
            "dl": user.data_level_max,
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
        "roles": [r.code for r in (current_user.roles or [])],
        "data_level_max": current_user.data_level_max,
        "dependency": current_user.dependency,
        "is_active": current_user.is_active,
    }


# ----------------------------
# RBAC + Niveles de dato
# ----------------------------
class SecurityChecker:
    def __init__(self, allowed_roles: Optional[List[str]] = None, min_data_level: int = 1):
        self.allowed_roles = allowed_roles
        self.min_data_level = min_data_level

    def __call__(self, current_user: User = Depends(get_current_user)):
        user_role_codes = [r.code for r in (current_user.roles or [])]

        # 1) Nivel de dato
        if current_user.data_level_max < self.min_data_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere nivel de datos {self.min_data_level} (Usted: {current_user.data_level_max})",
            )

        # 2) Roles (si aplican)
        if self.allowed_roles:
            # TI_ADMIN como superuser para gestión
            if "TI_ADMIN" in user_role_codes:
                return current_user

            has_role = any(role in user_role_codes for role in self.allowed_roles)
            if not has_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. Se requiere uno de los siguientes roles: {', '.join(self.allowed_roles)}",
                )

        return current_user


def require_role(roles: List[str]):
    return SecurityChecker(allowed_roles=roles)


def require_data_level(level: int):
    return SecurityChecker(min_data_level=level)


# Roles comunes (helpers)
is_admin = SecurityChecker(allowed_roles=["TI_ADMIN", "FUNC_ADMIN"])
is_data_owner = SecurityChecker(allowed_roles=["DATA_OWNER"])
institutional_access = SecurityChecker(min_data_level=2)
restricted_access = SecurityChecker(min_data_level=3)


# ----------------------------
# Compat guards (legacy imports)
# ----------------------------
# Algunos módulos (ej: api/ingesta.py) importan:
# from api.auth import admin_only, analyst_or_admin
# Estos guards mantienen compatibilidad.

def admin_only(current_user: User = Depends(get_current_user)):
    role_codes = [r.code for r in (current_user.roles or [])]
    if not any(r in role_codes for r in ("TI_ADMIN", "FUNC_ADMIN")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def analyst_or_admin(current_user: User = Depends(get_current_user)):
    role_codes = [r.code for r in (current_user.roles or [])]
    if not any(r in role_codes for r in ("TI_ADMIN", "FUNC_ADMIN", "ANALYST")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Analyst or admin only")
    return current_user

def ingestion_operator(current_user: User = Depends(get_current_user)):
    role_codes = [r.code for r in (current_user.roles or [])]
    allowed = ("TI_ADMIN", "FUNC_ADMIN", "ANALYST", "SOURCE_UPLOADER", "STEWARD")
    if not any(role in role_codes for role in allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ingestion access required")
    return current_user
