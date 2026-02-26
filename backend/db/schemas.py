from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: List[str] = []
    data_level_max: int = 1

# Permission Schema
class PermissionBase(BaseModel):
    code: str
    name: str
    module: str
    data_level_required: int

class Permission(PermissionBase):
    id: UUID
    class Config:
        from_attributes = True

# Role Schema
class RoleBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None

class Role(RoleBase):
    id: UUID
    permissions: List[Permission] = []
    class Config:
        from_attributes = True

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    dependency: Optional[str] = None
    position: Optional[str] = None
    data_level_max: int = 1
    is_active: bool = True

class UserCreate(UserBase):
    password: str
    role_codes: List[str] = []

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    dependency: Optional[str] = None
    position: Optional[str] = None
    data_level_max: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

class User(UserBase):
    id: UUID
    roles: List[Role] = []
    created_at: datetime
    last_login_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Access Request Schemas
class AccessRequestCreate(BaseModel):
    requested_roles: List[str]
    requested_data_level: int
    justification: str
    duration_days: Optional[int] = 30

class AccessRequest(BaseModel):
    id: UUID
    user_id: UUID
    requested_roles: List[str]
    requested_data_level: int
    justification: str
    status: str
    created_at: datetime
    decided_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Audit Log Schema
class AuditLogBase(BaseModel):
    actor_user_id: Optional[UUID] = None
    action: str
    module: Optional[str] = None
    target_ref: Optional[dict] = None
    data_level: Optional[int] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLog(AuditLogBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True
