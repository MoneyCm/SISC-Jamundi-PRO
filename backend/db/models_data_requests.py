"""Solicitudes de datos a las dependencias que no publican solas (Inspecciones, Comisarías…).

El Observatorio pide los datos cada semana o cada mes (modelo operativo, sección 2). Cada
solicitud queda con fecha, plazo y estado, para saber quién respondió y quién no.
"""
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from db.session import Base

PROGRAMS = ("INSPECCIONES", "COMISARIAS", "OTRA")
CADENCES = ("SEMANAL", "QUINCENAL", "MENSUAL")
REQUEST_STATUSES = ("PEDIDA", "RECIBIDA", "INCOMPLETA", "SIN_RESPUESTA")


class DataEntity(Base):
    __tablename__ = "data_request_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    program = Column(String(20), nullable=False, default="OTRA")
    cadence = Column(String(20), nullable=False, default="SEMANAL")
    contact = Column(String(300))  # correo o persona a quien se pide
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DataRequest(Base):
    __tablename__ = "data_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("data_request_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    what = Column(String(300), nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    requested_on = Column(Date, nullable=False, index=True)
    due_on = Column(Date, nullable=False)
    channel = Column(String(60))
    status = Column(String(20), nullable=False, default="PEDIDA", index=True)
    received_on = Column(Date)
    note = Column(Text)
    created_by = Column(String(120), nullable=False)
    updated_by = Column(String(120))
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
