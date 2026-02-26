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

def create_test_excel():
    data = {
        "FECHA ACTUACION": ["2026-01-10", "2026-02-15"],
        "EXPEDIENTE": ["EXP-TEST-001", "EXP-TEST-002"],
        "MEDIDA": ["MULTA", "CIERRE"],
        "ESTADO": ["EN PROCESO", "PAGADO"],
        "MUNICIPIO": ["JAMUNDI", "JAMUNDI"],  # Sin tilde como dice el usuario
        "DEPARTAMENTO": ["VALLE DEL CAUCA", "VALLE DEL CAUCA"]
    }
    df = pd.DataFrame(data)
    
    # Save to bytes
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def test_ingestion():
    db = SessionLocal()
    try:
        content = create_test_excel()
        filename = "REPORTE MNEDIDAS GESTIONADAS 1 ENERO 18 FEBREERO 2026.xlsx"
        ingestor = RNMCIngestor(db)
        
        print(f"--- Iniciando Ingestión de prueba: {filename} ---")
        res = ingestor.process_file(content, filename)
        print("\nResultado JSON devuelto:")
        import json
        print(json.dumps(res, indent=4))
        
        # Verify if inserted/updated matches
        total_afectados = res.get('inserted', 0) + res.get('updated', 0)
        if total_afectados > 0:
            print("\n✅ EXITO: Registros procesados correctamente (JAMUNDI detectado).")
        else:
            print("\n❌ FALLO: No se procesaron registros.")
            
    except Exception as e:
        print(f"Error durante la prueba: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_ingestion()
