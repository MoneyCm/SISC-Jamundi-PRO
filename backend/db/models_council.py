"""Compromisos de los Consejos de Seguridad y su historial de seguimiento.

A diferencia de los expedientes de intervención (que nacen de una alerta), un compromiso
nace en un acta del Consejo. El equipo de la Secretaría actualiza su estado antes de cada
sesión; cada cambio queda en el historial con autor, fecha y nota.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from db.session import Base

# SIN_INFORMACION: importado de un acta, nadie ha reportado avance todavía.
COMMITMENT_STATUSES = ("SIN_INFORMACION", "PENDIENTE", "EN_CURSO", "CUMPLIDO", "NO_CUMPLIDO", "DESCARTADO")


class CouncilCommitment(Base):
    __tablename__ = "council_commitments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(40), nullable=False, unique=True, index=True)  # p. ej. CS-2026-018, COP-2026-003
    # Instancia donde nació: CONSEJO_SEGURIDAD, COMITE_ORDEN_PUBLICO, COMITE_CIVIL_CONVIVENCIA, ...
    instance = Column(String(40), nullable=False, default="CONSEJO_SEGURIDAD", index=True)
    kind = Column(String(20), nullable=False, default="COMPROMISO")  # COMPROMISO | ACUERDO
    origin_date = Column(Date, index=True)
    origin_act = Column(String(120))
    session_type = Column(String(60))
    text = Column(Text, nullable=False)
    responsible = Column(String(300))
    deadline_text = Column(String(200))
    deadline_date = Column(Date, index=True)
    status = Column(String(30), nullable=False, default="SIN_INFORMACION", index=True)
    validated = Column(String(30), nullable=False, default="PENDIENTE")  # PENDIENTE | VALIDADO
    priority = Column(String(30))
    theme = Column(String(120), index=True)
    territory = Column(String(200))
    mentions = Column(Integer, nullable=False, default=1)
    last_mention_date = Column(Date)
    source_ref = Column(Text)
    notes = Column(Text)
    extra = Column(JSONB, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=0)
    updated_by = Column(String(120))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CouncilActRead(Base):
    """Acta leída por el SISC: propuestas pendientes de confirmar y resultado de la confirmación."""

    __tablename__ = "council_act_reads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    instance = Column(String(40), nullable=False)
    act_number = Column(String(20))
    act_date = Column(Date)
    reading = Column(JSONB, nullable=False)  # propuestas, advertencias, compromisos releídos
    status = Column(String(20), nullable=False, default="PENDIENTE")  # PENDIENTE | CONFIRMADA | HISTORICA (solo análisis)
    result = Column(JSONB)
    created_by = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_by = Column(String(120))
    confirmed_at = Column(DateTime(timezone=True))


class CouncilCommitmentUpdate(Base):
    __tablename__ = "council_commitment_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commitment_id = Column(UUID(as_uuid=True), ForeignKey("council_commitments.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    action = Column(String(30), nullable=False)  # IMPORTADO | ESTADO | EDICION
    previous_status = Column(String(30))
    new_status = Column(String(30))
    note = Column(Text)
    evidence_url = Column(Text)
    username = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
