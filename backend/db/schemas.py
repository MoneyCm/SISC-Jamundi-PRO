from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str
    role_id: int

class User(UserBase):
    id: UUID
    role_id: int

    class Config:
        from_attributes = True

# Role Schema
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class Role(RoleBase):
    id: int

    class Config:
        from_attributes = True
