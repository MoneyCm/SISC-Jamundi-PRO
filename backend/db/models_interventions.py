"""Expediente y revisiones inmutables de decisiones del Observatorio."""
import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.session import Base


class InterventionCase(Base):
    __tablename__ = "intervention_cases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Origen: una alerta del SISC o un compromiso del Consejo (al menos uno).
    alert_id = Column(UUID(as_uuid=True), ForeignKey("intelligence_alerts.id"), nullable=True, index=True)
    commitment_code = Column(String(40), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="BORRADOR")
    document = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InterventionRevision(Base):
    __tablename__ = "intervention_revisions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("intervention_cases.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    action = Column(String(30), nullable=False)
    document = Column(JSONB, nullable=False)
    user_id = Column(String(120), nullable=False)
    username = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_intervention_revision"),)
