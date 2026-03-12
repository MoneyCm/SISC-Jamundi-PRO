from sqlalchemy import Column, Integer, String, Date, Time, DateTime, JSON, ForeignKey, Boolean, Text, Float, Index, UniqueConstraint, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import datetime
from .session import Base

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fuente_codigo = Column(String(50), nullable=False, index=True) # POLICIA_SEMANAL
    hash_archivo = Column(String(64), index=True)
    filename = Column(String(255))
    total_filas = Column(Integer, default=0)
    aprobadas = Column(Integer, default=0)
    con_observacion = Column(Integer, default=0)
    rechazadas = Column(Integer, default=0)
    duplicadas = Column(Integer, default=0)
    fuera_territorio = Column(Integer, default=0)
    georreferenciadas = Column(Integer, default=0)
    usuario_carga = Column(String(100))
    fecha_inicio = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_fin = Column(DateTime)
    resumen = Column(JSONB) # Top conductas, etc.
    status = Column(String(50), default="IN_PROGRESS") # COMPLETED, FAILED

class IngestionIssue(Base):
    __tablename__ = "ingestion_issues"
    id = Column(Integer, primary_key=True, index=True)
    ingestion_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), index=True)
    fila = Column(Integer)
    regla = Column(String(100))
    descripcion = Column(Text)
    severidad = Column(String(20)) # ERROR, WARNING
    valor_leido = Column(String(255))

class StagingPoliciaSemanal(Base):
    __tablename__ = "stg_policia_semanal"
    id = Column(BigInteger, primary_key=True, index=True)
    ingestion_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), index=True)
    fila_origen = Column(Integer)
    payload_json = Column(JSONB)
    columnas_normalizadas = Column(JSONB)
    fecha_carga = Column(DateTime, default=datetime.datetime.utcnow)
    hash_archivo = Column(String(64))

class CatalogoConductaFuente(Base):
    __tablename__ = "catalogo_conductas_fuente"
    id = Column(Integer, primary_key=True, index=True)
    fuente_codigo = Column(String(50), index=True) # POLICIA_SEMANAL
    valor_fuente = Column(String(200), index=True)
    valor_estandar = Column(String(200)) # Delito homologado
    categoria_delito = Column(String(100)) # Categoria general
    activo = Column(Boolean, default=True)
    
    __table_args__ = (UniqueConstraint('fuente_codigo', 'valor_fuente', name='uq_source_value'),)

from sqlalchemy import BigInteger

class HechoSeguridad(Base):
    __tablename__ = "hechos_seguridad"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fuente_codigo = Column(String(50), nullable=False, index=True) # POLICIA_SEMANAL
    id_fuente = Column(String(100), index=True) # HECHOS_ID
    ingestion_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), index=True)
    
    conducta_original = Column(String(255))
    conducta_estandar = Column(String(255), index=True)
    categoria_delito = Column(String(100), index=True)
    
    fecha_evento = Column(Date, nullable=False, index=True)
    hora_evento = Column(Time)
    semana_num = Column(Integer, index=True)
    dia_semana = Column(String(20))
    
    sexo = Column(String(50))
    edad = Column(Integer)
    grupo_edad = Column(String(50))
    
    zona = Column(String(50))
    arma_medio = Column(String(100))
    modalidad = Column(String(100))
    movil_agresor = Column(String(100))
    movil_victima = Column(String(100))
    clase_sitio = Column(String(150))
    
    barrio_original = Column(String(150))
    barrio_normalizado = Column(String(150), index=True)
    vereda_original = Column(String(150))
    vereda_normalizada = Column(String(150), index=True)
    
    comuna = Column(String(50))
    corregimiento = Column(String(50))
    municipio = Column(String(100), default="JAMUNDI", index=True)
    
    estado_calidad = Column(String(50)) # APROBADO, CON_OBSERVACION
    fingerprint = Column(String(64), index=True)
    
    fecha_reporte_fuente = Column(DateTime)
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)
    usuario_ingesta = Column(String(100))

    __table_args__ = (
        Index('idx_hechos_source_id', 'fuente_codigo', 'id_fuente'),
        Index('idx_hechos_fingerprint', 'fuente_codigo', 'fingerprint'),
    )
