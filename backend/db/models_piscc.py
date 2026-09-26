"""Seguimiento semestral de las 43 acciones del PISCC 2024-2027.

Cada semestre, cada entidad responsable reporta el avance de sus acciones (PISCC 9.1). Una fila
por acción y semestre: el avance acumulado del cuatrienio al cierre del semestre, su estado y el
soporte que lo respalda. El catálogo de acciones vive en data/piscc/acciones_2024_2027.json.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from db.session import Base

ACTION_STATUSES = ("SIN_INICIAR", "EN_EJECUCION", "CUMPLIDA", "SUSPENDIDA")


class PisccActionReport(Base):
    __tablename__ = "piscc_action_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_code = Column(String(10), nullable=False, index=True)  # I-01 ... IV-09
    semester = Column(String(7), nullable=False, index=True)  # 2026-1, 2026-2
    value = Column(Float)  # avance acumulado del cuatrienio al cierre del semestre, en la unidad del indicador
    status = Column(String(20), nullable=False, default="EN_EJECUCION")
    reporting_entity = Column(String(200))  # quién envió el reporte
    evidence = Column(Text)  # soporte: oficio, enlace, acta
    note = Column(Text)
    received_on = Column(Date)
    created_by = Column(String(120), nullable=False)
    updated_by = Column(String(120))
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("action_code", "semester", name="uq_piscc_action_semester"),)
