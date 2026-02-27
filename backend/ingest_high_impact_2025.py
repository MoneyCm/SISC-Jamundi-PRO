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
    # Hash robusto para evitar duplicados basado en fecha, genero, zona y cantidad
    # Convertimos row a dict para manejar mejor los nulos
    d = row.to_dict()
    key_string = f"{dataset_name}-{d.get('fecha_hecho','NA')}-{d.get('sexo','X')}-{d.get('zona','X')}-{d.get('cantidad','1')}"
    return hashlib.sha256(key_string.encode()).hexdigest()

def ingest_csv(filename, dataset_label):
    db = SessionLocal()
    print("Iniciando ingesta de " + dataset_label + "...")
    
    try:
        df = pd.read_csv(filename)
        df['fecha_dt'] = pd.to_datetime(df['fecha_hecho'], errors='coerce')
        # Filtramos por 2024 en adelante para SISC PRO
        df = df[df['fecha_dt'].dt.year >= 2024].copy()
        
        print("Registros actuales (2024-2026) encontrados: " + str(len(df)))
        
        count = 0
        skipped = 0
        
        for _, row in df.iterrows():
            fp = generate_fingerprint(row, dataset_label)
            
            # Evitar duplicados
            exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.event_fingerprint == fp).first()
            if exists:
                skipped += 1
                continue
            
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
            count += 1
            
            if count % 200 == 0:
                db.commit()
                print("   ... insertados " + str(count) + " ...")

        db.commit()
        print("RESULTADO: " + dataset_label + " -> Insertados: " + str(count) + " | Duplicados: " + str(skipped))
        return count

    except Exception as e:
        print("Error en " + dataset_label + ": " + str(e))
        db.rollback()
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
            total += ingest_csv(f_path, label)
        else:
            print("Saltando " + label + ": archivo no encontrado")
            
    print("\n✅ PROCESO COMPLETADO. Total registros 2024-2026 inyectados: " + str(total))
