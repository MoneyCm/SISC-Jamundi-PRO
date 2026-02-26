from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, BigInteger, text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid
from .session import Base

class DqReport(Base):
    __tablename__ = "dq_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    filename = Column(String(255), nullable=False)
    source_name = Column(String(100))
    rows_total = Column(Integer)
    min_date = Column(DateTime, nullable=True)
    max_date = Column(DateTime, nullable=True)
    
    schema_ok = Column(Boolean, default=True)
    missing_cols = Column(JSONB) # List of missing required columns
    extra_cols = Column(JSONB)   # List of extra columns found
    
    # Scores (0.0 to 1.0)
    score_overall = Column(Float)
    score_completeness = Column(Float)
    score_validity = Column(Float)
    score_consistency = Column(Float)
    score_uniqueness = Column(Float)
    semaforo = Column(String(20)) # VERDE, AMARILLO, ROJO
    
    # Detailed Data
    report_json = Column(JSONB) # Profiling, detailed stats, rule summaries
    sample_json = Column(JSONB) # Small subset of rows (e.g. duplicates, errors) for UI
    
    issues = relationship("DqIssue", back_populates="report", cascade="all, delete-orphan")

class DqIssue(Base):
    __tablename__ = "dq_issues"
    
    id = Column(BigInteger, primary_key=True, index=True)
    report_id = Column(UUID(as_uuid=True), ForeignKey("dq_reports.id", ondelete="CASCADE"), nullable=False)
    severity = Column(String(20)) # ERROR, WARNING, INFO
    field = Column(String(100))    # Column name
    rule = Column(String(255))     # Rule description
    count = Column(Integer)        # Number of occurrences
    example = Column(JSONB)        # Example row(s) or value(s)
    
    report = relationship("DqReport", back_populates="issues")
