import pandas as pd
import sys
import os
import hashlib
from datetime import datetime
import logging

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingesta_robusta")

# Ajustar path para importar desde backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from db.session import SessionLocal
    from db.models_intelligence import NationalCrimeStats
except ImportError:
    # Fallback si no está en el path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from db.session import SessionLocal
    from db.models_intelligence import NationalCrimeStats

def generate_fingerprint(row_dict, dataset_name):
    # Hash robusto basado en los valores de las columnas
    key_string = f"{dataset_name}-{row_dict.get('fecha_hecho','NA')}-{row_dict.get('genero','X')}-{row_dict.get('cantidad','1')}-{row_dict.get('cod_muni','76364')}"
    return hashlib.sha256(key_string.encode()).hexdigest()

def ingest_csv_robusto(filename, dataset_label):
    db = SessionLocal()
    logger.info(f"🚀 Iniciando ingesta ROBUSTA de {dataset_label} desde {filename}...")
    
    try:
        # Leer SIN cabecera porque el CSV no tiene nombres de columnas
        df = pd.read_csv(filename, header=None, names=['fecha', 'cod_depto', 'depto', 'cod_muni', 'muni', 'zona', 'sexo', 'cantidad'])
        
        # Limpieza de datos
        df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce')
        df = df.dropna(subset=['fecha_dt'])
        
        logger.info(f"Registros válidos encontrados: {len(df)}")
        
        count = 0
        skipped = 0
        
        for _, row in df.iterrows():
            # Mapear datos a nombres consistentes
            data = {
                'fecha_hecho': str(row['fecha']),
                'genero': str(row['sexo']).upper(),
                'cantidad': int(row['cantidad']) if pd.notnull(row['cantidad']) else 1,
                'cod_muni': str(row['cod_muni'])
            }
            
            fp = generate_fingerprint(data, dataset_label)
            
            # Evitar duplicados
            exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.event_fingerprint == fp).first()
            if exists:
                skipped += 1
                continue
            
            new_stat = NationalCrimeStats(
                source_id='DATOS_GOV_MINDEFENSA',
                departamento=str(row['depto']).upper(),
                municipio=str(row['muni']).upper(),
                municipio_normalizado='JAMUNDI',
                codigo_dane=str(row['cod_muni']),
                fecha_hecho=row['fecha_dt'].date(),
                anio=int(row['fecha_dt'].year),
                mes=int(row['fecha_dt'].month),
                tipo_delito=dataset_label,
                genero=data['genero'],
                cantidad=data['cantidad'],
                event_fingerprint=fp,
                fuente_archivo=os.path.basename(filename),
                fecha_ingesta=datetime.utcnow()
            )
            db.add(new_stat)
            count += 1
            
            if count % 200 == 0:
                db.commit()
                logger.info(f"   ... insertados {count} ...")

        db.commit()
        logger.info(f"✅ RESULTADO: {dataset_label} -> Insertados: {count} | Duplicados: {skipped}")
        return count

    except Exception as e:
        logger.error(f"❌ Error en {dataset_label}: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

def run_full_ingestion():
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    files = [
        (os.path.join(base_path, "JAMUNDI_LATEST_HOMICIDIO.csv"), "HOMICIDIO"),
        (os.path.join(base_path, "JAMUNDI_LATEST_HURTO_PERSONAS.csv"), "HURTO_PERSONAS"),
        (os.path.join(base_path, "JAMUNDI_LATEST_HURTO_COMERCIO.csv"), "HURTO_COMERCIO"),
        (os.path.join(base_path, "JAMUNDI_LATEST_HURTO_RESIDENCIAS.csv"), "HURTO_RESIDENCIAS")
    ]
    
    total = 0
    for f_path, label in files:
        if os.path.exists(f_path):
            total += ingest_csv_robusto(f_path, label)
        else:
            logger.warning(f"Saltando {label}: archivo no encontrado")
            
    logger.info(f"\n🏆 PROCESO COMPLETADO. Total registros inyectados: {total}")
    return total

if __name__ == "__main__":
    run_full_ingestion()
