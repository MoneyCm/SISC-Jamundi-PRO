import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .session import Base


class MedicinaLegalRun(Base):
    __tablename__ = "medicina_legal_runs"

    id = Column(String(80), primary_key=True)
    status = Column(String(40), nullable=False, default="IN_PROGRESS", index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    finished_at = Column(DateTime(timezone=True))
    source_cutoff_date = Column(Date, index=True)
    datasets = Column(JSONB, nullable=False, default=dict)
    details = Column(JSONB, nullable=False, default=dict)


class MedicinaLegalSnapshot(Base):
    __tablename__ = "medicina_legal_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(80), ForeignKey("medicina_legal_runs.id"), nullable=False, index=True)
    dataset_key = Column(String(40), nullable=False, index=True)
    dataset_id = Column(String(20), nullable=False, index=True)
    cutoff_date = Column(Date, nullable=False, index=True)
    payload_sha256 = Column(String(64), nullable=False, index=True)
    schema_version = Column(String(32), nullable=False)
    source_row_count = Column(BigInteger)
    filtered_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    discarded_count = Column(Integer, default=0)
    discard_reasons = Column(JSONB, nullable=False, default=dict)
    definitive = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (
        UniqueConstraint("dataset_id", "cutoff_date", "payload_sha256", name="uq_ml_snapshot_version"),
        Index("idx_ml_snapshot_latest", "dataset_key", "cutoff_date"),
    )


class MedicinaLegalRecord(Base):
    __tablename__ = "medicina_legal_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("medicina_legal_snapshots.id"), nullable=False, index=True)
    dataset_key = Column(String(40), nullable=False, index=True)
    record_key = Column(String(64), nullable=False)
    year_hecho = Column(Integer, index=True)
    month_hecho = Column(Integer, index=True)
    codigo_dane_departamento = Column(String(2), index=True)
    codigo_dane_municipio = Column(String(5), index=True)
    departamento = Column(Text)
    municipio = Column(Text, index=True)
    contexto = Column(Text, index=True)
    sexo = Column(String(50), index=True)
    grupo_edad = Column(String(80))
    zona = Column(String(80))
    escenario = Column(Text)
    mecanismo_causal = Column(Text)
    circunstancia = Column(Text)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (
        UniqueConstraint("snapshot_id", "record_key", name="uq_ml_snapshot_record"),
        Index("idx_ml_record_period", "dataset_key", "year_hecho", "month_hecho"),
    )