from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Boolean, Text, text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .session import Base, engine, SessionLocal, get_db

def create_tables():
    try:
        from db.models_intelligence import NationalCrimeStats, IngestionLog, TerritorialContext
        from db.models_dq import DqReport, DqIssue
        from db.models_mindefensa import MindefensaAsset
        from db.models_alerts import IntelligenceAlert
        from db.models_auth import User, Role, Permission, AuditLog, AccessRequest
        
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS location_geom GEOMETRY(Point, 4326);"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS dq_report_id UUID;"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS ingestion_id UUID;"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS source_name VARCHAR(100);"))
                
                # Columnas para Inteligencia / Fuerza Pública
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS institucion VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS accion VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS categoria_grado VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS codigo_dane VARCHAR(20);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS barrio VARCHAR(150);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS semana INTEGER;"))
                
                conn.commit()
                print("Estructura de Base de Datos verificada con éxito.")
            except Exception as e:
                print(f"Nota: No se pudo verificar la estructura de la tabla: {e}")
    except Exception as e:
        print(f"Error fatal durante create_tables: {e}")

# Re-exportar User y Role para compatibilidad con código existente
from .models_auth import User, Role

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
    location_geom = Column(Text) 
    
    dq_report_id = Column(UUID(as_uuid=True), ForeignKey("dq_reports.id"), nullable=True)
    ingestion_id = Column(UUID(as_uuid=True), nullable=True)
    source_name = Column(String(100))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    
    event_type = relationship("EventType")

class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False) 
    barrio = Column(String(100), nullable=False)
    status = Column(String(50), default="PENDIENTE") 
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    author_name = Column(String(100))

class SafetyFront(Base):
    __tablename__ = "safety_fronts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    barrio = Column(String(100), nullable=False)
    leader_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    status = Column(String(50), default="ACTIVO") 
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class SecureReport(Base):
    __tablename__ = "secure_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo = Column(String(100), nullable=False)
    barrio = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    descripcion = Column(Text, nullable=False)
    es_anonimo = Column(Boolean, default=True)
    nombre = Column(String(100), nullable=True)
    contacto = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
