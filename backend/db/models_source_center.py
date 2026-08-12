from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from .session import Base


class SourceConnectorState(Base):
    __tablename__ = "source_connector_states"

    connector_code = Column(String(50), primary_key=True)
    status = Column(String(40), nullable=False, default="NEEDS_REVIEW")
    quality_status = Column(String(40), nullable=False, default="INCOMPLETE")
    period_label = Column(String(160), nullable=True)
    source_cutoff_date = Column(Date, nullable=True, index=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_change_detected_at = Column(DateTime(timezone=True), nullable=True)
    record_count = Column(BigInteger, nullable=True)
    indicator_count = Column(Integer, nullable=True)
    warnings = Column(JSON, nullable=False, default=list)
    details = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
