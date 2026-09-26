"""Estudios y recomendaciones del Observatorio del Delito.

Un estudio responde una pregunta sobre un fenómeno en un territorio y un periodo.
Sus recomendaciones se presentan a una instancia (Consejo, comité, despacho) y se
siguen hasta que alguien decide: si se aceptan, se enlazan al compromiso que las ejecuta.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from db.session import Base

STUDY_STATUSES = ("ABIERTO", "EN_CURSO", "CERRADO")
# RESERVADO: solo el equipo de análisis y la dirección lo ven.
ACCESS_LEVELS = ("INSTITUCIONAL", "RESERVADO")
RECOMMENDATION_STATUSES = ("PROPUESTA", "PRESENTADA", "ACEPTADA", "RECHAZADA", "EN_EJECUCION", "CUMPLIDA")
PRIORITIES = ("ALTA", "MEDIA", "BAJA")


class ObservatoryStudy(Base):
    __tablename__ = "observatory_studies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), nullable=False, unique=True, index=True)  # OBS-2026-001
    title = Column(String(200), nullable=False)
    question = Column(Text, nullable=False)  # la pregunta que el estudio responde
    phenomenon = Column(String(120))
    territory = Column(String(200))
    period_start = Column(Date)
    period_end = Column(Date)
    sources = Column(JSONB, nullable=False, default=list)
    hypotheses = Column(Text)
    findings = Column(Text)
    status = Column(String(20), nullable=False, default="ABIERTO", index=True)
    access_level = Column(String(20), nullable=False, default="INSTITUCIONAL")
    created_by = Column(String(120), nullable=False)
    updated_by = Column(String(120))
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ObservatoryRecommendation(Base):
    __tablename__ = "observatory_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), nullable=False, unique=True, index=True)  # REC-2026-001
    study_id = Column(UUID(as_uuid=True), ForeignKey("observatory_studies.id", ondelete="SET NULL"), index=True)
    title = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    addressed_to = Column(String(200))  # instancia o dependencia que debe decidir
    priority = Column(String(10), nullable=False, default="MEDIA")
    status = Column(String(20), nullable=False, default="PROPUESTA", index=True)
    presented_on = Column(Date)
    decided_on = Column(Date)
    decision_note = Column(Text)
    commitment_code = Column(String(40), index=True)  # compromiso que la ejecuta
    due_date = Column(Date)
    history = Column(JSONB, nullable=False, default=list)
    created_by = Column(String(120), nullable=False)
    updated_by = Column(String(120))
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
