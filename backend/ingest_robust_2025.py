import pandas as pd
import sys
import os
import hashlib
from datetime import datetime

# Ajustar path para importar desde backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SessionLocal
from db.models_intelligence import NationalCrimeStats

def generate_fingerprint(row, dataset_name):
    d = row.to_dict()
    # Usamos más campos para el hash para evitar colisiones accidentales
    key_string = f"{dataset_name}-{d.get('fecha_hecho','NA')}-{d.get('sexo','X')}-{d.get('zona','X')}-{d.get('cantidad','1')}-{d.get('cod_muni','NA')}"
    return hashlib.sha256(key_string.encode()).hexdigest()

def ingest_csv_robust(filename, dataset_label):
    db = SessionLocal()
    print(f"📊 Procesando {dataset_label}...")
    
    try:
        df = pd.read_csv(filename)
        df['fecha_dt'] = pd.to_datetime(df['fecha_hecho'], errors='coerce')
        df = df[df['fecha_dt'].dt.year >= 2024].copy()
        
        count = 0
        skipped = 0
        
        for _, row in df.iterrows():
            fp = generate_fingerprint(row, dataset_label)
            
            # Verificación individual para no romper la transacción
            exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.event_fingerprint == fp).first()
            if exists:
                skipped += 1
                continue
            
            try:
                new_stat = NationalCrimeStats(
                    source_id='DATOS_GOV_MINDEFENSA',
                    departamento=row.get('departamento', 'VALLE DEL CAUCA'),
                    municipio=row.get('municipio', 'JAMUNDI'),
                    municipio_normalizado='JAMUNDI',
                    codigo_dane=str(row.get('cod_muni', '76364')),
                    fecha_hecho=row['fecha_dt'].date(),
                    anio=int(row['fecha_dt'].year),
                    mes=int(row['fecha_dt'].month),
                    tipo_delito=dataset_label,
                    genero=row.get('sexo', 'NO REPORTADO'),
                    cantidad=int(row.get('cantidad', 1)),
                    event_fingerprint=fp,
                    fuente_archivo=os.path.basename(filename),
                    fecha_ingesta=datetime.utcnow()
                )
                db.add(new_stat)
                db.commit() # Commit individual para ser robustos
                count += 1
            except Exception:
                db.rollback()
                skipped += 1

        print(f"✅ {dataset_label}: {count} nuevos, {skipped} saltados.")
        return count

    except Exception as e:
        print(f"❌ Error en {dataset_label}: {e}")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    files = [
        ("backend/JAMUNDI_LATEST_HOMICIDIO.csv", "HOMICIDIO"),
        ("backend/JAMUNDI_LATEST_HURTO_PERSONAS.csv", "HURTO_PERSONAS"),
        ("backend/JAMUNDI_LATEST_HURTO_COMERCIO.csv", "HURTO_COMERCIO"),
        ("backend/JAMUNDI_LATEST_HURTO_RESIDENCIAS.csv", "HURTO_RESIDENCIAS")
    ]
    
    total = 0
    for f_path, label in files:
        if os.path.exists(f_path):
            total += ingest_csv_robust(f_path, label)
            
    print(f"
🚀 FIN. Total registros nuevos: {total}")
