from sqlalchemy import Column, String, DateTime, Text, text, Index, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from .session import Base
import uuid
from datetime import datetime


class IntelligenceAlert(Base):
    __tablename__ = "intelligence_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)  # ej: "RNMC"
    alert_type = Column(String(100), nullable=False)  # ej: "RNMC_BACKLOG"
    severity = Column(String(20), nullable=False)  # "HIGH", "MEDIUM", "LOW"
    title = Column(String(255), nullable=False)
    body_md = Column(Text, nullable=False)
    entity_ref = Column(JSONB, nullable=False)  # {source_id, event_fingerprint}
    metrics = Column(JSONB, nullable=False)  # {dias, valor_neto, ...}
    dedupe_key = Column(String(255), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="OPEN", index=True)  # "OPEN", "ACK", "DISMISSED"

    # Scoring y Priorización (Fase 3)
    action_score = Column(Float, nullable=True)  # 0-100
    priority_tier = Column(String(10), nullable=True, index=True)  # "P1", "P2", "P3"
    recommended_action = Column(Text, nullable=True)
    rationale_md = Column(Text, nullable=True)
    ai_rationale_md = Column(Text, nullable=True)
    ai_provider = Column(String(50), nullable=True)
    ai_request_id = Column(String(100), nullable=True)
    scored_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # --- Bandeja operativa: revisión humana separada de la evidencia ---
    review_state = Column(String(20), nullable=False, default="PENDIENTE", index=True)
    # PENDIENTE | EN_ANALISIS | REVISADA | DESCARTADA. REVISADA = examinada, no resuelta.
    review_version = Column(Integer, nullable=False, default=0)  # bloqueo optimista
    # --- Linaje retrospectivo: identidad común por indicador+territorio+período ---
    lineage_key = Column(String(255), nullable=True, index=True)
    previous_evaluation_id = Column(UUID(as_uuid=True), nullable=True)
    superseded_by = Column(UUID(as_uuid=True), nullable=True)
    supersede_note = Column(Text, nullable=True)

    # Indices adicionales
    Index("idx_alerts_status_created", status, created_at.desc())
    Index("idx_alerts_source_status", source, status)
    Index("idx_alerts_status_score", status, action_score.desc())


class IntelligenceAlertSnapshot(Base):
    """
    Snapshot inmutable del ranking de alertas (ej. RNMC).
    Guarda solo metadatos y payload agregado, sin PII ni expediente completo.
    """

    __tablename__ = "intelligence_alert_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source = Column(String(50), nullable=False)  # "RNMC"
    filters = Column(JSONB, nullable=False)  # {status, tiers, from,to, limit, ...}
    scoring_config = Column(JSONB, nullable=False)
    payload_json = Column(JSONB, nullable=False)  # lista de alertas (sin PII)
    payload_sha256 = Column(String(64), nullable=False, unique=True)

    __table_args__ = (
        Index("idx_alert_snapshots_source_created", "source", "created_at"),
    )


class AlertReview(Base):
    """Revisión humana de una alerta. La evidencia calculada es inmutable;
    cada valoración queda aquí con autoría y fecha del servidor.

    Estados: PENDIENTE | EN_ANALISIS | REVISADA | DESCARTADA.
    DESCARTADA exige motivo. REVISADA = examinada, no problema resuelto.
    """

    __tablename__ = "alert_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("intelligence_alerts.id"), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # estado nuevo aplicado
    prev_state = Column(String(20), nullable=False)
    new_state = Column(String(20), nullable=False)
    username = Column(String(120), nullable=False)
    user_id = Column(String(120), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_alert_reviews_alert_created", "alert_id", "created_at"),
    )

