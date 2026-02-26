import os
import sys
import pandas as pd
import logging
import io
import gc
from datetime import datetime

# Configurar path para importar backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.models import SessionLocal
from services.excel_processor import NationalStatsProcessor
from services.ingest_rnmc import RNMCIngestor
from db.models_intelligence import NationalCrimeStats, IngestionFile, RNMCMeasure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bulk_loader")

def process_historical_files(directory):
    db = SessionLocal()
    stats_processor = NationalStatsProcessor()
    rnmc_ingestor = RNMCIngestor(db)
    
    files = [f for f in os.listdir(directory) if f.lower().endswith('.xlsx') or f.lower().endswith('.xls')]
    
    print(f"--- Iniciando Carga Masiva desde: {directory} ---")
    
    for filename in files:
        file_path = os.path.join(directory, filename)
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            
            # Intentar primero como RNMC (es más específico)
            print(f"\n>> Analizando: {filename}")
            try:
                # Comprobación ligera antes de invocar el ingestor completo
                df_head = pd.read_excel(io.BytesIO(content), nrows=20, header=None)
                all_text = " ".join(df_head.astype(str).values.flatten()).upper()
                
                if "MEDIDA" in all_text and "ACTUACION" in all_text:
                    res = rnmc_ingestor.process_file(content, filename)
                    print(f"   [RNMCIngestor] {res.get('inserted', 0)} insertados, {res.get('updated', 0)} actualizados.")
                    continue
            except Exception:
                pass # No es RNMC o falló la detección

            # Intentar como SIEDCO / Delitos
            try:
                records = list(stats_processor.process_excel(content, filename))
                if records:
                    from sqlalchemy.dialects.postgresql import insert
                    count = 0
                    for r in records:
                        r.pop('fuente_type', None)
                        stmt = insert(NationalCrimeStats).values(r)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=['source_id', 'event_fingerprint'],
                            set_={
                                "cantidad": NationalCrimeStats.cantidad + r["cantidad"],
                                "fuente_archivo": r["fuente_archivo"]
                            }
                        )
                        db.execute(stmt)
                        count += 1
                    db.commit()
                    print(f"   [NationalProcessor] {count} registros procesados.")
                else:
                    print(f"   [Skip] No se extrajeron datos de Jamundí en {filename}.")
            except Exception as e:
                print(f"   ❌ Fallo en procesamiento de delitos: {e}")
                db.rollback()

        except Exception as e:
            print(f"   ❌ Error leyendo {filename}: {e}")
        
        # GC to keep memory low
        gc.collect()

    db.close()
    print("\n--- CARGA COMPLETADA ---")

if __name__ == "__main__":
    downloads_path = "C:/Users/USER/Downloads"
    if os.path.exists(downloads_path):
        process_historical_files(downloads_path)
    else:
        print(f"Error: No se encontró la ruta {downloads_path}")
