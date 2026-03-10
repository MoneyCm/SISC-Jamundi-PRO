from sqlalchemy import Column, String, Integer, Date, DateTime, Numeric, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from .session import Base

class InspeccionExpediente(Base):
    __tablename__ = "inspeccion_expedientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_expediente = Column(String(100), unique=True, nullable=False, index=True)
    departamento = Column(String(100), default="VALLE DEL CAUCA")
    municipio = Column(String(100), default="JAMUNDÍ")
    localidad = Column(String(150), index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    medidas = relationship("InspeccionMedida", back_populates="expediente", cascade="all, delete-orphan")

class InspeccionMedida(Base):
    __tablename__ = "inspeccion_medidas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expediente_id = Column(UUID(as_uuid=True), ForeignKey("inspeccion_expedientes.id", ondelete="CASCADE"))
    nombre_medida = Column(Text, nullable=False)
    estado_actual = Column(String(100), default="ABIERTO", index=True)
    tipo_seguimiento = Column(String(100))
    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    dias_duracion = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    expediente = relationship("InspeccionExpediente", back_populates="medidas")
    actuaciones = relationship("InspeccionActuacion", back_populates="medida", cascade="all, delete-orphan")
    finanza = relationship("InspeccionFinanza", back_populates="medida", uselist=False, cascade="all, delete-orphan")

class InspeccionActuacion(Base):
    __tablename__ = "inspeccion_actuaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medida_id = Column(UUID(as_uuid=True), ForeignKey("inspeccion_medidas.id", ondelete="CASCADE"))
    fecha_actuacion = Column(DateTime(timezone=True), nullable=False, index=True)
    id_registrador = Column(String(100))
    funcionario = Column(String(255))
    anotacion = Column(Text)
    otros_medios_prueba = Column(Text)
    fingerprint_hash = Column(String(64), unique=True, index=True)
    fuente_archivo = Column(String(255))
    ingestion_id = Column(UUID(as_uuid=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    medida = relationship("InspeccionMedida", back_populates="actuaciones")

class InspeccionFinanza(Base):
    __tablename__ = "inspeccion_finanzas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medida_id = Column(UUID(as_uuid=True), ForeignKey("inspeccion_medidas.id", ondelete="CASCADE"), unique=True)
    valor_neto = Column(Numeric(15, 2), default=0)
    valor_pagado = Column(Numeric(15, 2), default=0)
    valor_interes = Column(Numeric(15, 2), default=0)
    valor_descuento = Column(Numeric(15, 2), default=0)
    valor_coactivo = Column(Numeric(15, 2), default=0)
    fecha_pago = Column(Date)
    entidad_pago = Column(String(150))
    comprobante_pago = Column(String(100))
    numero_cuenta = Column(String(100))
    fecha_liquidacion = Column(Date)
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    medida = relationship("InspeccionMedida", back_populates="finanza")
