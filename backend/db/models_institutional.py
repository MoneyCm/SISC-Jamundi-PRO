import uuid
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .session import Base


class InstitutionalDataBatch(Base):
    __tablename__ = "institutional_data_batches"
    __table_args__ = (
        UniqueConstraint("program", "reporting_entity", "period", "version", name="uq_institutional_batch_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program = Column(String(80), nullable=False, index=True)
    reporting_entity = Column(String(180), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)
    cutoff_date = Column(Date, nullable=False)
    reporting_basis = Column(String(20), nullable=False, default="CUMULATIVE")
    source_reference = Column(String(500), nullable=False)
    source_filename = Column(String(255))
    version = Column(Integer, nullable=False, default=1)
    validation_status = Column(String(20), nullable=False, default="PENDING", index=True)
    submitted_by = Column(String(100), nullable=False)
    approved_by = Column(String(100))
    review_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))

    indicators = relationship("InstitutionalIndicator", back_populates="batch", cascade="all, delete-orphan")


class InstitutionalIndicator(Base):
    __tablename__ = "institutional_indicators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("institutional_data_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    indicator = Column(String(220), nullable=False, index=True)
    category = Column(String(160))
    value = Column(Numeric(16, 2), nullable=False)
    unit = Column(String(40), nullable=False, default="casos")
    is_public = Column(Boolean, nullable=False, default=True)
    privacy_threshold = Column(Integer, nullable=False, default=10)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("InstitutionalDataBatch", back_populates="indicators")

class InstitutionalAgentRun(Base):
    __tablename__ = "institutional_agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("institutional_data_batches.id", ondelete="SET NULL"), index=True)
    source_filename = Column(String(255), nullable=False)
    source_sha256 = Column(String(64), nullable=False, index=True)
    extractor_version = Column(String(30), nullable=False, default="1.0")
    status = Column(String(30), nullable=False, default="RECEIVED", index=True)
    summary = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    batch = relationship("InstitutionalDataBatch")
    findings = relationship("InstitutionalAgentFinding", back_populates="run", cascade="all, delete-orphan")


class InstitutionalAgentFinding(Base):
    __tablename__ = "institutional_agent_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("institutional_agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(60), nullable=False)
    severity = Column(String(20), nullable=False, default="INFO")
    code = Column(String(80), nullable=False)
    message = Column(Text, nullable=False)
    evidence = Column(Text)
    blocks_publication = Column(Boolean, nullable=False, default=False)
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("InstitutionalAgentRun", back_populates="findings")