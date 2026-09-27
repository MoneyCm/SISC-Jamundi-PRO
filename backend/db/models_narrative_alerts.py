"""Alertas Narrativas: mensajes cortos, listos para WhatsApp, y su historial.

Cada mensaje resume las tres variaciones más significativas de un periodo (semanal o mensual)
y el estado de los compromisos del Consejo de Seguridad. El texto generado no se borra: las
ediciones quedan como revisiones con autor y fecha, y la evidencia calculada se guarda aparte.
"""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from db.session import Base

FREQUENCIES = ("SEMANAL", "MENSUAL", "CONSEJO", "SEMESTRAL", "ANUAL")
# BORRADOR: se puede editar. ENVIADO: congelado. REEMPLAZADO: una entrega corregida generó otra versión.
ALERT_STATUSES = ("BORRADOR", "ENVIADO", "DESCARTADO", "REEMPLAZADO")


class NarrativeAlert(Base):
    __tablename__ = "narrative_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frequency = Column(String(10), nullable=False, index=True)  # SEMANAL | MENSUAL | CONSEJO | SEMESTRAL | ANUAL
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False, index=True)
    previous_start = Column(Date, nullable=False)
    previous_end = Column(Date, nullable=False)
    data_cutoff = Column(Date, nullable=False)
    source_version_id = Column(String(64), nullable=False)  # entrega policial usada (ingestion_runs.id)
    rules_version = Column(String(20), nullable=False)
    trigger = Column(String(20), nullable=False, default="MANUAL")  # PROGRAMADA | CARGA (al cargar la sábana) | MANUAL
    generated_text = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="BORRADOR", index=True)
    evidence = Column(JSONB, nullable=False)
    superseded_by = Column(UUID(as_uuid=True), nullable=True)
    version = Column(Integer, nullable=False, default=0)  # bloqueo optimista
    created_by = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_by = Column(String(120))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    sent_by = Column(String(120))
    sent_at = Column(DateTime(timezone=True))
    sent_note = Column(String(300))  # a quién o a qué grupo se envió
    # Alerta para el Consejo: la sesión para la que se preparó.
    occasion_date = Column(Date, index=True)
    occasion_label = Column(String(120))

    # Sin restricción única: una misma entrega puede servir a dos sesiones del Consejo. La unicidad
    # (periodo o sesión + entrega) la garantiza el servicio con un bloqueo consultivo.
    __table_args__ = (Index("ix_narrative_alerts_period", "frequency", "period_end"),)


class NarrativeAlertRevision(Base):
    __tablename__ = "narrative_alert_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("narrative_alerts.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # GENERADO | EDITADO | ACTUALIZADO | ENVIADO | DESCARTADO | REEMPLAZADO
    text = Column(Text, nullable=False)
    note = Column(Text)
    username = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
