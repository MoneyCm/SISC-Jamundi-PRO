from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, SmallInteger, Table, BigInteger, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .session import Base
import uuid
import datetime

class Role(Base):
    __tablename__ = "roles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    users = relationship("User", secondary="user_roles", back_populates="roles")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False, index=True) # users, ingesta, rnmc, etc.
    data_level_required = Column(SmallInteger, default=1) # 1: Público, 2: Institucional, 3: Restringido

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150))
    is_active = Column(Boolean, default=True)
    
    dependency = Column(String(100)) # Secretaría / Dependencia
    position = Column(String(100))   # Cargo
    data_level_max = Column(SmallInteger, default=1) # 1, 2, 3
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    last_login_at = Column(DateTime)
    expires_at = Column(DateTime) # Vigencia obligatoria para N3

    roles = relationship("Role", secondary="user_roles", back_populates="users")

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_by = Column(UUID(as_uuid=True)) # ID of user who assigned it
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime) # Vigencia del rol para este usuario

class AccessRequest(Base):
    __tablename__ = "access_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    requested_roles = Column(JSONB) # List of role codes
    requested_permissions = Column(JSONB) # List of permission codes
    requested_data_level = Column(SmallInteger) # 1/2/3
    
    justification = Column(Text, nullable=False)
    duration_days = Column(Integer)
    
    status = Column(String(20), default="PENDING", index=True) # PENDING, APPROVED, REJECTED, EXPIRED
    
    approved_by_func_admin = Column(UUID(as_uuid=True))
    approved_by_data_owner = Column(UUID(as_uuid=True)) # Required for N3
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    decided_at = Column(DateTime)

    user = relationship("User", foreign_keys=[user_id])

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id = Column(UUID(as_uuid=True), index=True)
    action = Column(String(50), nullable=False, index=True) # LOGIN, EXPORT, etc.
    module = Column(String(50), index=True)
    target_ref = Column(JSONB) # {user_id, report_id, etc.}
    data_level = Column(SmallInteger)
    ip = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
