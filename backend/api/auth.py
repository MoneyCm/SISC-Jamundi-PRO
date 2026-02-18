from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from core.security import verify_password, create_access_token, SECRET_KEY, ALGORITHM
from db.models import get_db, User, Role
from db.schemas import Token, TokenData

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="ingesta/auth/login") # Ajustado al prefijo en main.py si es necesario

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
        print(f"AUTH DEBUG: Token recibido (len={len(token) if token else 0})")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        print(f"AUTH DEBUG: Payload decodificado: sub={username}, role={role}")
        if username is None:
            print("AUTH DEBUG: Username es None")
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError as e:
        print(f"AUTH DEBUG: JWTError: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"AUTH DEBUG: Exception: {e}")
        raise credentials_exception
        
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Obtener nombre del rol
    role = db.query(Role).filter(Role.id == user.role_id).first()
    role_name = role.name if role else "Público"
    
    access_token = create_access_token(
        data={"sub": user.username, "role": role_name}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active
    }

# --- LOGICA DE ROLES Y PERMISOS ---

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        role = db.query(Role).filter(Role.id == current_user.role_id).first()
        role_name = role.name if role else "Público"
        
        # El Administrador siempre tiene acceso a todo
        if role_name == "Administrador (Observatorio)":
            return current_user
            
        if role_name not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de los siguientes roles: {', '.join(self.allowed_roles)}"
            )
        return current_user

# Dependencias para usar en los otros archivos
# Dependencias para usar en los otros archivos
# 1. Admin: Todo el poder
admin_only = RoleChecker(["Administrador (Observatorio)"])

# 2. Nivel Estratégico + Táctico (Analistas, Ejecutivos, Admin)
executive_access = RoleChecker([
    "Administrador (Observatorio)", 
    "Analista Institucional", 
    "Tomador de Decisiones (Ejecutivo)"
])

# 3. Nivel Operativo + Táctico (Fuerza Pública, Analistas, Admin)
operational_access = RoleChecker([
    "Administrador (Observatorio)", 
    "Analista Institucional", 
    "Enlace Fuerza Pública"
])

# 4. Acceso General Institucional (Todos los roles logueados)
institutional_access = RoleChecker([
    "Administrador (Observatorio)", 
    "Analista Institucional", 
    "Tomador de Decisiones (Ejecutivo)", 
    "Enlace Fuerza Pública"
])

# legacy (mantener por compatibilidad si algo lo usa)
analyst_or_admin = RoleChecker(["Administrador (Observatorio)", "Analista Institucional"])
public_access = RoleChecker(["Administrador (Observatorio)", "Analista Institucional", "Ciudadano (Modo Abierto)"])
