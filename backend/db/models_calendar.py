"""Fechas de sesión del Consejo de Seguridad para el calendario operativo del Observatorio.

El Consejo sesiona en la última semana de cada mes, sin día fijo. Cuando se conoce la fecha
exacta se registra aquí; si no, el calendario usa la última semana del mes como estimación.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from db.session import Base


class CouncilSession(Base):
    __tablename__ = "council_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance = Column(String(40), nullable=False, default="CONSEJO_SEGURIDAD")
    session_date = Column(Date, nullable=False, index=True)
    note = Column(Text)
    created_by = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("instance", "session_date", name="uq_council_session_date"),)
