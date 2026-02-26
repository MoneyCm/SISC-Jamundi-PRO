import pandas as pd
import io
import os
import sys
import logging

# Configurar logging para ver la salida del ingestor
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sisc_api")

# Add current dir/backend to path to import backend modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from db.models import SessionLocal
    from services.ingest_rnmc import RNMCIngestor
except ImportError as e:
    print(f"Error importando módulos: {e}")
    sys.exit(1)

def test_real_file():
    db = SessionLocal()
    try:
        file_path = "backend/rnmc_test.xlsx"
        if not os.path.exists(file_path):
            print(f"Error: No existe el archivo {file_path}")
            return

        with open(file_path, "rb") as f:
            content = f.read()

        filename = "REPORTE MNEDIDAS GESTIONADAS 1 ENERO 18 FEBREERO 2026.xlsx"
        ingestor = RNMCIngestor(db)
        
        print(f"--- Iniciando Ingestión de archivo REAL: {filename} ---")
        res = ingestor.process_file(content, filename)
        
        print("\nResultado JSON devuelto:")
        import json
        print(json.dumps(res, indent=4))
        
        # Verify if inserted/updated matches
        total_afectados = res.get('inserted', 0) + res.get('updated', 0)
        if total_afectados > 0:
            print(f"\n✅ EXITO: Registros procesados correctamente: {total_afectados}")
        else:
            print("\n❌ FALLO: No se procesaron registros (0).")
            if "municipio_uniques" in res:
                print(f"Municipios detectados: {res['municipio_uniques']}")
            if "df_shape" in res:
                print(f"Shape original: {res['df_shape']}")
            
    except Exception as e:
        print(f"Error durante la prueba: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_real_file()
