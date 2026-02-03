from sqlalchemy import create_engine, Column, Integer, String, Date, Time, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import os

# Configuración de la URL de la base de datos
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi")

# Fix para Render/SQLAlchemy: cambiar postgres:// por postgresql://
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_tables():
    Base.metadata.create_all(bind=engine)

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    role_id = Column(Integer, ForeignKey("roles.id"))
    is_active = Column(Boolean, default=True)

class EventType(Base):
    __tablename__ = "event_types"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(100))
    is_delicto = Column(Boolean, default=True)

class Event(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(100))
    event_type_id = Column(Integer, ForeignKey("event_types.id"))
    occurrence_date = Column(Date, nullable=False)
    occurrence_time = Column(Time, nullable=False)
    barrio = Column(String(100))
    estado = Column(String(50), default="Abierto")
    descripcion = Column(Text)
    # Nota: PostGIS geom se trata con SQL crudo en los endpoints por ahora
    
    event_type = relationship("EventType")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
