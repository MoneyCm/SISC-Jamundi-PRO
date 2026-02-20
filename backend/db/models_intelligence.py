from sqlalchemy import Column, Integer, String, Date, Float, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from .models import Base
import datetime

class NationalCrimeStats(Base):
    __tablename__ = "national_crime_stats"

    id = Column(Integer, primary_key=True, index=True)
    departamento = Column(String(100), nullable=False, index=True)
    municipio = Column(String(100), nullable=False)
    municipio_normalizado = Column(String(100), nullable=False, index=True) # Para búsquedas insensibles a tildes/mayúsculas
    codigo_dane = Column(String(20)) # Opcional, para mapas futuros
    
    fecha_hecho = Column(Date, nullable=False, index=True)
    anio = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    
    tipo_delito = Column(String(100), nullable=False, index=True) # Homicidio, Hurto Personas, etc.
    modalidad = Column(String(100)) # Arma de fuego, Blanca, etc.
    
    cantidad = Column(Integer, default=1)
    
    # Identificador único para evitar duplicados (hash de fecha + municipio + delito + cantidad)
    hash_registro = Column(String(64), unique=True, index=True)
    
    # Metadatos de origen
    fuente_archivo = Column(String(255)) # Nombre del archivo Excel origen
    fecha_corte_mindefensa = Column(Date) # Fecha de corte reportada en el archivo
    fecha_ingesta = Column(DateTime, default=datetime.datetime.utcnow)

    # Índices compuestos para optimizar comparativas
    __table_args__ = (
        Index('idx_ncs_anio_municipio', 'anio', 'municipio_normalizado'),
        Index('idx_ncs_fecha_delito', 'fecha_hecho', 'tipo_delito'),
    )

class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id = Column(Integer, primary_key=True, index=True)
    fecha_inicio = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_fin = Column(DateTime)
    estado = Column(String(50)) # IN_PROGRESS, SUCCESS, ERROR
    archivos_procesados = Column(Integer, default=0)
    registros_insertados = Column(Integer, default=0)
    errores = Column(Text)
    detalles = Column(JSONB) # Detalles técnicos del scraping
