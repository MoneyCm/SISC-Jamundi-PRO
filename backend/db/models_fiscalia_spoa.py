import datetime
import uuid

from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .session import Base


class FiscaliaSpoaRun(Base):
    __tablename__ = "fiscalia_spoa_runs"

    id = Column(String(80), primary_key=True)
    status = Column(String(40), nullable=False, default="IN_PROGRESS", index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    finished_at = Column(DateTime(timezone=True))
    source_cutoff_date = Column(Date, index=True)
    datasets = Column(JSONB, nullable=False, default=dict)
    bulletin_path = Column(Text)
    bulletin_sha256 = Column(String(64), index=True)
    details = Column(JSONB, nullable=False, default=dict)


class FiscaliaSpoaSnapshot(Base):
    __tablename__ = "fiscalia_spoa_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(80), ForeignKey("fiscalia_spoa_runs.id"), nullable=False, index=True)
    dataset_key = Column(String(20), nullable=False, index=True)
    dataset_id = Column(String(20), nullable=False, index=True)
    cutoff_date = Column(Date, nullable=False, index=True)
    metadata_sha256 = Column(String(64), nullable=False)
    payload_sha256 = Column(String(64), nullable=False, index=True)
    schema_version = Column(String(32), nullable=False)
    source_row_count = Column(BigInteger)
    filtered_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    discarded_count = Column(Integer, default=0)
    discard_reasons = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (
        UniqueConstraint("dataset_id", "cutoff_date", "payload_sha256", name="uq_spoa_snapshot_version"),
        Index("idx_spoa_snapshot_latest", "dataset_key", "cutoff_date"),
    )


class FiscaliaSpoaRecord(Base):
    __tablename__ = "fiscalia_spoa_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("fiscalia_spoa_snapshots.id"), nullable=False, index=True)
    dataset_key = Column(String(20), nullable=False, index=True)
    record_key = Column(String(64), nullable=False)
    entity_anonimizado = Column(Text, nullable=False)
    proceso_anonimizado = Column(Text, index=True)
    delito_id = Column(String(50), index=True)
    delito = Column(Text)
    year_hecho = Column(Integer, index=True)
    month_hecho = Column(Integer, index=True)
    estado = Column(String(80), index=True)
    etapa = Column(String(100), index=True)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (
        UniqueConstraint("snapshot_id", "record_key", name="uq_spoa_snapshot_record"),
        Index("idx_spoa_record_period", "dataset_key", "year_hecho", "month_hecho"),
    )

