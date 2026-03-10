import pandas as pd
import hashlib
import logging
import unicodedata
from datetime import datetime, date
from typing import Dict, List, Optional
import io
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida, InspeccionActuacion, InspeccionFinanza
from db.models_intelligence import IngestionFile
from services.geocoding_service import GeocodingService
from sqlalchemy import text

logger = logging.getLogger("sisc_api")

class InspeccionService:
    def __init__(self, db: Session):
        self.db = db

    def normalize_text(self, text: str) -> str:
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        return text.upper().strip()

    def parse_date(self, val) -> Optional[datetime]:
        if pd.isna(val): return None
        if isinstance(val, (datetime, date)): return pd.to_datetime(val)
        try: return pd.to_datetime(str(val), dayfirst=True)
        except: return None

    def to_float(self, v):
        if pd.isna(v): return 0.0
        try: return float(str(v).replace('$', '').replace(',', '').strip())
        except: return 0.0

    def generate_fingerprint(self, row: Dict) -> str:
        """EXPEDIENTE + MEDIDA + FECHA_ACTUACION + ANOTACION"""
        exp = str(row.get('EXPEDIENTE', '')).strip()
        med = self.normalize_text(str(row.get('MEDIDA', '')))
        f_act = self.parse_date(row.get('FECHA_ACTUACION'))
        f_str = f_act.isoformat() if f_act else "NO_DATE"
        anot = self.normalize_text(str(row.get('ANOTACION', '')))
        
        raw = f"{exp}|{med}|{f_str}|{anot}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def ingest_excel(self, file_content: bytes, filename: str, user_id: Optional[str] = None) -> Dict:
        df = pd.read_excel(io.BytesIO(file_content))
        
        # Normalizar nombres de columnas (quitar espacios, tildes, a mayúsculas)
        df.columns = [self.normalize_text(c).replace(' ', '_') for c in df.columns]
        
        # Filtro Jamundí
        if 'MUNICIPIO' in df.columns:
            df = df[df['MUNICIPIO'].astype(str).str.upper().str.contains('JAMUNDI')].copy()

        if df.empty:
            return {"status": "ERROR", "message": "No se encontraron registros de Jamundí o el archivo está vacío."}

        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        
        for _, row_raw in df.iterrows():
            row = row_raw.to_dict()
            try:
                # 1. Gestionar Expediente
                nro_exp = str(row.get('EXPEDIENTE', '')).strip()
                if not nro_exp or nro_exp.lower() == 'nan':
                     stats["skipped"] += 1
                     continue

                expediente = self.db.query(InspeccionExpediente).filter_by(numero_expediente=nro_exp).first()
                loc_name = self.normalize_text(str(row.get('LOCALIDAD', '')))
                
                if not expediente:
                    expediente = InspeccionExpediente(
                        numero_expediente=nro_exp,
                        localidad=loc_name,
                        departamento=self.normalize_text(str(row.get('DTO', ''))),
                        municipio=self.normalize_text(str(row.get('MUNICIPIO', '')))
                    )
                    self.db.add(expediente)
                    self.db.flush()

                # Georreferenciación (PostGIS)
                coords = GeocodingService.get_coords_for_localidad(loc_name)
                if coords:
                    lat, lng = coords
                    # Usar SQL crudo para ST_SetSRID ya que SQLAlchemy puro sin GeoAlchemy2 puede ser complejo
                    self.db.execute(
                        text("UPDATE inspeccion_expedientes SET geom_punto = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                        {"lng": lng, "lat": lat, "id": expediente.id}
                    )

                # 2. Gestionar Medida
                nombre_medida = self.normalize_text(str(row.get('MEDIDA', '')))
                medida = self.db.query(InspeccionMedida).filter_by(
                    expediente_id=expediente.id, 
                    nombre_medida=nombre_medida
                ).first()

                if not medida:
                    medida = InspeccionMedida(
                        expediente_id=expediente.id,
                        nombre_medida=nombre_medida
                    )
                    self.db.add(medida)
                    self.db.flush()

                # Actualizar campos de la medida
                medida.estado_actual = self.normalize_text(str(row.get('ESTADO', '')))
                medida.tipo_seguimiento = self.normalize_text(str(row.get('TIPO_SEGUIMIENTO', '')))
                medida.fecha_inicio = self.parse_date(row.get('FECHA_INICIO'))
                medida.fecha_fin = self.parse_date(row.get('FECHA_FIN'))
                try: 
                    medida.dias_duracion = int(row.get('DIAS', 0))
                except: 
                    if medida.fecha_inicio and medida.fecha_fin:
                        medida.dias_duracion = (medida.fecha_fin - medida.fecha_inicio).days
                
                # 3. Gestionar Actuación (Idempotente)
                fp = self.generate_fingerprint(row)
                existing_act = self.db.query(InspeccionActuacion).filter_by(fingerprint_hash=fp).first()
                
                if not existing_act:
                    actuacion = InspeccionActuacion(
                        medida_id=medida.id,
                        fecha_actuacion=self.parse_date(row.get('FECHA_ACTUACION')) or datetime.now(),
                        id_registrador=str(row.get('ID_REGISTRA', '')),
                        funcionario=str(row.get('FUNCIONARIO', '')),
                        anotacion=str(row.get('ANOTACION', '')),
                        otros_medios_prueba=str(row.get('OTROS_MEDIOS_PRUEBA', '')),
                        fingerprint_hash=fp,
                        fuente_archivo=filename
                    )
                    self.db.add(actuacion)
                    self.db.flush() # Asegurar que sea visible para consultas en el mismo loop
                    stats["inserted"] += 1
                else:
                    stats["skipped"] += 1

                # 4. Gestionar Finanzas
                finanza = self.db.query(InspeccionFinanza).filter_by(medida_id=medida.id).first()
                if not finanza:
                    finanza = InspeccionFinanza(medida_id=medida.id)
                    self.db.add(finanza)
                    self.db.flush()
                
                finanza.valor_neto = self.to_float(row.get('VALOR_NETO'))
                finanza.valor_pagado = self.to_float(row.get('VALOR_PAGADO'))
                finanza.valor_interes = self.to_float(row.get('VALOR_INTERES'))
                finanza.valor_descuento = self.to_float(row.get('VALOR_DESCUENTO'))
                finanza.valor_coactivo = self.to_float(row.get('VALOR_COACTIVO'))
                finanza.fecha_pago = self.parse_date(row.get('FECHA_PAGO'))
                finanza.entidad_pago = str(row.get('ENTIDAD_PAGO', ''))
                finanza.comprobante_pago = str(row.get('COMPROBANTE_PAGO', ''))
                finanza.numero_cuenta = str(row.get('NUMERO_CUENTA', ''))
                finanza.fecha_liquidacion = self.parse_date(row.get('FECHA_LIQUIDACION'))

            except Exception as e:
                logger.error(f"Error procesando fila {row.get('EXPEDIENTE')}: {e}")
                stats["errors"] += 1

        self.db.commit()
        return stats
