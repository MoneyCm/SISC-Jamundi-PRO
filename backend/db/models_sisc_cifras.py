from sqlalchemy import Column, Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
import uuid

from .session import Base


class SiscCifrasPublication(Base):
    __tablename__ = "sisc_cifras_publications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(180), nullable=False)
    edition_type = Column(String(50), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    status = Column(String(40), nullable=False, default="DRAFT", index=True)
    created_by = Column(String(120), nullable=True)
    template_code = Column(String(80), nullable=False, default="SISC_CIFRAS_1080x1350")
    format = Column(String(40), nullable=False, default="CAROUSEL_1080x1350")
    source_codes = Column(JSONB, nullable=False, default=list)
    publication_json = Column(JSONB, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
