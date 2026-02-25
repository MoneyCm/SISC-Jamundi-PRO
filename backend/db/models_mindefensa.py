from sqlalchemy import Column, String, BigInteger, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from db.models import Base

class MindefensaAsset(Base):
    __tablename__ = "mindefensa_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_code = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String)
    category = Column(String, nullable=True) # Grupo al que pertenece
    file_url = Column(String, nullable=False)
    source_page_url = Column(String)
    
    last_checked_at = Column(DateTime(timezone=True))
    last_seen_etag = Column(String, nullable=True)
    last_seen_last_modified = Column(String, nullable=True)
    last_seen_content_length = Column(BigInteger, nullable=True)
    
    status = Column(String, nullable=False, default="UNKNOWN") # UNKNOWN/UNCHANGED/UPDATED/ERROR
    last_change_detected_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
