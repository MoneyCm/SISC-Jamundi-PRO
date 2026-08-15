from sqlalchemy import Column, Integer, String, Date, Float, DateTime, Index, ForeignKey, Table, UniqueConstraint, Text, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from .session import Base
import datetime
import uuid

class IngestionFile(Base):
    __tablename__ = "ingestion_files"

    ingestion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False) # source_id
    file_hash = Column(String(64), index=True)
    ingested_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Trazabilidad extendida
    inserted_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    records_count = Column(Integer, default=0) # Total procesados
    periodo_detectado = Column(String(100)) # Legacy
    periodo_detectado_min = Column(Date)
    periodo_detectado_max = Column(Date)
    anios_incluidos = Column(JSONB) # List of years
    semanas_incluidas = Column(JSONB) # List or range of weeks
    
    status = Column(String(20), default="COMPLETED") # COMPLETED, REJECTED, FAILED

    __table_args__ = (
        UniqueConstraint('source_type', 'file_hash', name='uq_source_file_hash'),
    )

class TerritorialContext(Base):
    __tablename__ = "territorial_context"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(50), nullable=False, index=True) # ASPERSION
    fuente_id = Column(String(50), index=True) # Legacy
    departamento = Column(String(100), index=True)
    municipio = Column(String(100), index=True)
    codigo_muni = Column(Integer, index=True)
    codigo_depto = Column(Integer, index=True)
    
    fecha_hecho = Column(Date, nullable=False, index=True)
    anio = Column(Integer, index=True)
    mes = Column(Integer)
    
    cantidad = Column(Float, nullable=False) # Hectáreas / Otras medidas
    unidad_medida = Column(String(50)) # HECTAREA
    
    fuente_archivo = Column(String(255))
    event_fingerprint = Column(String(64), index=True)
    hash_registro = Column(String(64), unique=True, index=True) # Legacy
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('idx_tc_source_fingerprint', 'source_id', 'event_fingerprint', unique=True),
        Index('idx_tc_fuente_municipio', 'source_id', 'municipio'),
    )

class NationalCrimeStats(Base):
    __tablename__ = "national_crime_stats"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(50), nullable=False, index=True) # SEM_POLICIA, AFECTACION_FUERZA_PUBLICA
    departamento = Column(String(100), nullable=False, index=True)
    municipio = Column(String(100), nullable=False)
    municipio_normalizado = Column(String(100), nullable=False, index=True)
    codigo_dane = Column(String(20))
    
    fecha_hecho = Column(Date, nullable=False, index=True)
    anio = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    
    tipo_delito = Column(String(100), nullable=False, index=True)
    modalidad = Column(String(100))
    barrio = Column(String(150), index=True)
    semana = Column(Integer, index=True)
    
    institucion = Column(String(100), index=True)
    accion = Column(String(100), index=True)
    categoria_grado = Column(String(100))

    genero = Column(String(50), index=True)
    grupo_etario = Column(String(50), index=True)
    
    cantidad = Column(Integer, default=1)
    
    event_fingerprint = Column(String(64), index=True)
    hash_registro = Column(String(64), unique=True, index=True) # Legacy
    
    fuente_archivo = Column(String(255))
    fecha_corte_mindefensa = Column(Date)
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('idx_ncs_source_fingerprint', 'source_id', 'event_fingerprint', unique=True),
        Index('idx_ncs_anio_municipio', 'anio', 'municipio_normalizado'),
        Index('idx_ncs_fecha_delito', 'fecha_hecho', 'tipo_delito'),
    )


class NationalReferenceCoverage(Base):
    """Verified municipal coverage accompanying compact national aggregates."""

    __tablename__ = "national_reference_coverage"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(50), nullable=False, index=True)
    tipo_delito = Column(String(100), nullable=False, index=True)
    anio = Column(Integer, nullable=False, index=True)
    municipality_codes = Column(JSONB, nullable=False)
    fecha_corte_mindefensa = Column(Date)
    fuente_archivo = Column(String(255))
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source_id', 'tipo_delito', 'anio', name='uq_reference_coverage_scope'),
    )

class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id = Column(Integer, primary_key=True, index=True)
    fecha_inicio = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_fin = Column(DateTime)
    estado = Column(String(50)) # IN_PROGRESS, SUCCESS, ERROR
    archivos_procesados = Column(Integer, default=0)
    registros_insertados = Column(Integer, default=0)
    errores = Column(Text)
    detalles = Column(JSONB) # Detalles técnicos del scraping

class ReportRun(Base):
    __tablename__ = "report_runs"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(50), nullable=False) # SEMANAL, MENSUAL, YTD
    source_id = Column(String(50), nullable=False) # SEM_POLICIA
    period_key = Column(String(50), nullable=False) # 2026-W08, 2026-M02, 2026-YTD
    
    status = Column(String(20), default="COMPLETED") # COMPLETED, FAILED, SKIPPED
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    output_json = Column(JSONB)
    output_markdown = Column(Text)
    
    # Auditoría de Forzado
    forced = Column(Boolean, default=False)
    forced_by = Column(String(100))
    forced_reason = Column(String(255))
    
    meta_info = Column(JSONB) # { "fecha_corte": "...", "cobertura": "..." }
    report_name = Column(String(255), nullable=True)

    # Trazabilidad de Exportación PDF
    pdf_generated_at = Column(DateTime)
    pdf_path = Column(String(255))
    pdf_sha256 = Column(String(64))

    # Auditoría Descarga
    download_count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('report_type', 'source_id', 'period_key', name='uq_report_period'),
    )

class ReportRecipient(Base):
    __tablename__ = "report_recipients"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, unique=True)
    name = Column(String(100))
    group_name = Column(String(50), nullable=False) # comite_semanal, consejo_mensual
    is_active = Column(Boolean, default=True)

class ReportDownloadToken(Base):
    __tablename__ = "report_download_tokens"
    id = Column(Integer, primary_key=True, index=True)
    report_run_id = Column(Integer, ForeignKey("report_runs.id"), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)



class ReportDownloadAudit(Base):
    __tablename__ = "report_download_audit"
    id = Column(Integer, primary_key=True, index=True)
    report_run_id = Column(Integer, ForeignKey("report_runs.id"))
    user_id = Column(UUID(as_uuid=True), nullable=True) # Si es por JWT
    token_id = Column(Integer, ForeignKey("report_download_tokens.id"), nullable=True) # Si es por Token temporal
    downloaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    ip_address = Column(String(45))

class ReportNotificationLog(Base):
    __tablename__ = "report_notification_log"
    id = Column(Integer, primary_key=True, index=True)
    report_run_id = Column(Integer, ForeignKey("report_runs.id"), nullable=False)
    group_name = Column(String(50), nullable=False)
    recipients_count = Column(Integer, default=0)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(20), default="SUCCESS") # SUCCESS, FAILED
    error_detail = Column(Text)

class IntelligenceLog(Base):
    __tablename__ = "intelligence_log"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    provider = Column(String(50), nullable=False)  # GEMINI, MISTRAL, FALLBACK
    model_name = Column(String(100), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    context_hash = Column(String(64), nullable=False)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # SUCCESS, ERROR, FALLBACK
    period_key = Column(String(50), nullable=True)
    source_id = Column(String(50), nullable=True)
    report_run_id = Column(Integer, ForeignKey("report_runs.id"), nullable=True)
    error_code = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)

class RNMCMeasure(Base):
    __tablename__ = "rnmc_measures"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(50), nullable=False, index=True, default="INSPECCION_MEDIDAS_RNMC")
    
    departamento = Column(String(100), index=True)
    municipio = Column(String(100), index=True)
    localidad = Column(String(150), index=True)
    
    expediente = Column(String(100), index=True)
    medida = Column(String(255), index=True)
    
    fecha_actuacion = Column(DateTime, nullable=False, index=True)
    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    dias = Column(Integer)
    
    tipo_seguimiento = Column(String(100), index=True)
    estado = Column(String(100), index=True)
    
    fecha_pago = Column(Date)
    entidad_pago = Column(String(150))
    valor_neto = Column(Float)
    valor_pagado = Column(Float)
    fecha_liquidacion = Column(Date)
    
    event_fingerprint = Column(String(64), index=True)
    fuente_archivo = Column(String(255))
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('idx_rnmc_source_fingerprint', 'source_id', 'event_fingerprint', unique=True),
        Index('idx_rnmc_municipio_fecha', 'municipio', 'fecha_actuacion'),
    )

class RNMCStatusHistory(Base):
    __tablename__ = "rnmc_status_history"
    id = Column(Integer, primary_key=True, index=True)
    measure_id = Column(Integer, ForeignKey("rnmc_measures.id"), nullable=False)
    source_id = Column(String(50), nullable=False)
    event_fingerprint = Column(String(64), nullable=False, index=True)
    
    estado_anterior = Column(String(100), nullable=False)
    estado_nuevo = Column(String(100), nullable=False)
    
    fecha_reportada = Column(DateTime)
    changed_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    fuente_archivo = Column(String(255))
    ingestion_id = Column(UUID(as_uuid=True))

    __table_args__ = (
        Index('idx_rnmc_hist_source_fp', 'source_id', 'event_fingerprint'),
    )



