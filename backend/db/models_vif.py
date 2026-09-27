"""Casos de violencia intrafamiliar atendidos por las Comisarías de Familia (anonimizados).

Cada comisaría entrega su base (Excel o CSV) en su propio formato. La entrega se previsualiza,
se confirma y queda registrada. Nunca se guardan nombres, documentos, teléfonos ni direcciones:
las columnas que los traen se descartan al leer el archivo, y el código interno del caso (si
viene) se guarda solo como huella irreversible para medir reincidencia.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from db.session import Base

ENTITIES = ("Comisaría Primera de Familia", "Comisaría Segunda de Familia")
DELIVERY_STATUSES = ("PREVISUALIZADA", "CONFIRMADA", "DESCARTADA")


class VifDelivery(Base):
    __tablename__ = "vif_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity = Column(String(120), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    sheet = Column(String(120))
    mapping = Column(JSONB, nullable=False)  # {campo: columna del archivo}
    dropped_columns = Column(JSONB, nullable=False, default=list)  # columnas con datos personales descartadas
    ignored_columns = Column(JSONB, nullable=False, default=list)  # columnas sin uso en el análisis
    # Filas crudas SOLO de las columnas permitidas, para reasignar columnas antes de confirmar.
    # Se borran al confirmar o descartar.
    staged_rows = Column(JSONB)
    summary = Column(JSONB, nullable=False, default=dict)
    period_start = Column(Date)
    period_end = Column(Date)
    status = Column(String(20), nullable=False, default="PREVISUALIZADA", index=True)
    created_by = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_by = Column(String(120))
    decided_at = Column(DateTime(timezone=True))


class VifCase(Base):
    __tablename__ = "vif_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity = Column(String(120), nullable=False, index=True)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("vif_deliveries.id"), nullable=False, index=True)
    record_key = Column(String(64), nullable=False)  # identidad estable de la atención dentro de la comisaría
    case_key = Column(String(64), index=True)  # huella del código interno del caso (reincidencia)
    fecha_atencion = Column(Date, nullable=False, index=True)
    lugar_original = Column(String(150))
    lugar = Column(String(150), index=True)  # nombre oficial si se reconoce
    lugar_reconocido = Column(String(20), nullable=False, default="NO")  # SI | NO | SIN_DATO
    sexo = Column(String(20), nullable=False, default="SIN_DATO")
    rango_edad = Column(String(30), nullable=False, default="SIN_DATO")
    tipos_violencia = Column(JSONB, nullable=False, default=list)
    relacion = Column(String(30), nullable=False, default="SIN_DATO")
    antecedentes = Column(String(10), nullable=False, default="SIN_DATO")  # SI | NO | SIN_DATO
    nivel_riesgo = Column(String(20), nullable=False, default="SIN_DATO")
    medidas = Column(JSONB, nullable=False, default=list)
    fecha_medida = Column(Date)
    seguimiento = Column(String(10), nullable=False, default="SIN_DATO")
    reincidencia = Column(String(10), nullable=False, default="SIN_DATO")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("entity", "record_key", name="uq_vif_case_entity_record"),)


class VifSetting(Base):
    """Sal persistente para las huellas de los códigos de caso (si no hay VIF_CASE_KEY_SECRET)."""

    __tablename__ = "vif_settings"

    key = Column(String(50), primary_key=True)
    value = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
