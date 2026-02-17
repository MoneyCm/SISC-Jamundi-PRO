from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt
import os
import bcrypt
from passlib.context import CryptContext

# Configuración
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key_for_development")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 día para desarrollo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        # Intentar bcrypt directo para evitar fallos de passlib en algunos entornos
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        # Fallback a passlib si bcrypt falla (por si el hash no es bcrypt)
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except:
            return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_pseudonym(original_id: str) -> str:
    """Genera un hash único irreversible para IDs de personas."""
    import hashlib
    # Salt interno para mayor seguridad
    salt = "sisc_jamundi_2025_secure_salt"
    return hashlib.sha256((original_id + salt).encode()).hexdigest()
