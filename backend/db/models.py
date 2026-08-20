from sqlalchemy import Column, Integer, String, Date, Time, ForeignKey, Boolean, Text, text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .session import Base, engine, SessionLocal, get_db

def create_tables():
    try:
        from db.models_intelligence import NationalCrimeStats, NationalReferenceCoverage, IngestionLog, TerritorialContext
        from db.models_dq import DqReport, DqIssue
        from db.models_mindefensa import MindefensaAsset
        from db.models_policia import PoliceAsset
        from db.models_source_center import SourceConnectorState
        from db.models_alerts import IntelligenceAlert
        from db.models_auth import User, Role, Permission, AuditLog, AccessRequest
        from db.models_inspecciones import InspeccionExpediente, InspeccionMedida, InspeccionActuacion, InspeccionFinanza
        from db.models_institutional import InstitutionalDataBatch, InstitutionalIndicator, InstitutionalAgentRun, InstitutionalAgentFinding
        from db.models_sisc_cifras import SiscCifrasPublication
        from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, IngestionIssue, StagingPoliciaSemanal, SabanaSnapshotRow, CatalogoConductaFuente
        
        with engine.connect() as conn:
            try:
                # 0. REPARACIÓN PRE-CREACIÓN: Transición Legacy a RBAC v2
                # Verificamos si la tabla roles existe y si su ID es ENTERO (legacy)
                check_roles = conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name = 'roles' AND column_name = 'id';")).fetchone()
                
                # Verificar si la tabla users tiene la nueva columna full_name
                check_users_new = conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'full_name';")).fetchone()
                
                legacy_detected = False
                if check_roles and check_roles[0] in ('integer', 'int4'): legacy_detected = True
                if not check_users_new: legacy_detected = True # Si no tiene full_name, es estructura antigua
                
                if legacy_detected:
                    print("[ALERTA] ESTRUCTURA LEGACY CRÍTICA DETECTADA (Roles o Usuarios antiguos). Limpiando...")
                    # Forzar borrado de todo el subsistema de Auth para recrearlo limpio
                    tables_to_drop = [
                        "role_permissions", "user_roles", "access_requests", 
                        "audit_log", "roles", "permissions", "user_permissions", "users"
                    ]
                    for table in tables_to_drop:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                    
                    conn.commit()
                    print("[OK] Tablas legacy eliminadas. El sistema las recreará con UUID.")
                else:
                    # Si ya es UUID, asegurar que tenga la columna 'code'
                    if check_roles:
                        conn.execute(text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS code VARCHAR(50) UNIQUE;"))
                        conn.commit()
                
                # 1. Crear extensiones necesarias
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
                conn.commit()
            except Exception as e:
                print(f"[AVISO] Error durante la fase PRE-CREACIÓN: {e}")
                # Si falla el commit anterior, intentamos seguir
                try: conn.rollback()
                except: pass

        # 2. Ahora sí, crear tablas según modelos actuales (SQLAlchemy)
        print("[Iniciando] Ejecutando Base.metadata.create_all...")
        Base.metadata.create_all(bind=engine)
        print("[OK] Base.metadata.create_all finalizado.")

        # 3. Ajustes post-creación (ALTER TABLE para columnas de negocio)
        with engine.connect() as conn:
            try:
                
                # Otras columnas necesarias
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS location_geom GEOMETRY(Point, 4326);"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS dq_report_id UUID;"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS ingestion_id UUID;"))
                conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS source_name VARCHAR(100);"))
                
                # Columnas para Inteligencia / Fuerza Pública
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS source_id VARCHAR(50);"))
                conn.execute(text("UPDATE national_crime_stats SET source_id = 'GENERIC_CRIME' WHERE source_id IS NULL;"))
                
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS institucion VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS accion VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS categoria_grado VARCHAR(100);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS codigo_dane VARCHAR(20);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS barrio VARCHAR(150);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS semana INTEGER;"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS genero VARCHAR(50);"))
                conn.execute(text("ALTER TABLE national_crime_stats ADD COLUMN IF NOT EXISTS grupo_etario VARCHAR(50);"))
                
                # Asegurar índice único para ON CONFLICT
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_ncs_source_fingerprint ON national_crime_stats (source_id, event_fingerprint);"))

                # Territorial Context
                conn.execute(text("ALTER TABLE territorial_context ADD COLUMN IF NOT EXISTS source_id VARCHAR(50);"))
                conn.execute(text("UPDATE territorial_context SET source_id = 'GENERIC_CONTEXT' WHERE source_id IS NULL;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_tc_source_fingerprint ON territorial_context (source_id, event_fingerprint);"))

                # RNMC Measures
                conn.execute(text("ALTER TABLE rnmc_measures ADD COLUMN IF NOT EXISTS source_id VARCHAR(50);"))
                conn.execute(text("UPDATE rnmc_measures SET source_id = 'INSPECCION_MEDIDAS_RNMC' WHERE source_id IS NULL;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_rnmc_source_fingerprint ON rnmc_measures (source_id, event_fingerprint);"))
                conn.execute(text("ALTER TABLE institutional_data_batches ADD COLUMN IF NOT EXISTS reporting_basis VARCHAR(20) DEFAULT 'CUMULATIVE';"))
                
                # --- Fase 1.5: columnas nuevas para contrato v1 ---
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS requested_filters JSONB;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS resolved_filters JSONB;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS schema_version VARCHAR(10);"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_url TEXT;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_data BYTEA;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_sha256 VARCHAR(64);"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS hash_integrity JSONB;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS suppressed_cells JSONB DEFAULT '[]'::jsonb;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS catalog_versions_used JSONB;"))
                conn.execute(text("ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS query_hash VARCHAR(64);"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_sisc_cifras_query_hash ON sisc_cifras_publications (query_hash) WHERE query_hash IS NOT NULL AND status != 'SUPERSEDED';"))
                
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
