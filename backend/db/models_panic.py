from sqlalchemy import Column, String, DateTime, Text, text, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .session import Base
import uuid
from datetime import datetime

class PanicAlert(Base):
    __tablename__ = "panic_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    
    # Detalle opcional
    note = Column(Text, nullable=True)
    
    # Metadatos del dispositivo/usuario
    device_info = Column(JSONB, nullable=True)
    
    # Estado de la alerta
    status = Column(String(20), nullable=False, default="OPEN", index=True) # OPEN, DISPATCHED, RESOLVED, FALSE_ALARM, DISMISSED
    
    # Evidencias (links a archivos subidos)
    evidence_urls = Column(JSONB, nullable=False, default=list) # ["url1", "url2"]
    
    # Auditoría y Trazabilidad
    assigned_to = Column(String(100), nullable=True) # Usuario que atiende
    ip_address = Column(String(45), nullable=True) # Dirección IP origen
    
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now)

class PanicEvidence(Base):
    __tablename__ = "panic_evidences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("panic_alerts.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50)) # image/jpeg, video/mp4
    file_size = Column(Float) # en bytes
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
