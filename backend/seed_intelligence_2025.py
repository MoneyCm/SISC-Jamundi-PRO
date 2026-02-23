import os
import sys
from datetime import datetime, date
import hashlib

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.models import SessionLocal
from db.models_intelligence import NationalCrimeStats

def seed_intelligence_2025():
    db = SessionLocal()
    try:
        # Datos de prueba para Jamundí 2025
        # Simulamos algunos delitos comunes para que el dashboard tenga contenido
        municipio = "JAMUNDI"
        depto = "VALLE DEL CAUCA"
        anio = 2025
        
        delitos = [
            {"tipo": "Homicidio Intencional", "cantidades": [5, 4, 6, 3, 5, 4, 5, 6, 7, 5, 4, 5]},
            {"tipo": "Hurto Personas", "cantidades": [45, 38, 52, 41, 48, 44, 50, 55, 60, 48, 42, 45]},
            {"tipo": "Lesiones Personales", "cantidades": [12, 10, 15, 11, 13, 12, 14, 16, 18, 14, 12, 13]},
            {"tipo": "Hurto a Comercio", "cantidades": [8, 6, 10, 7, 9, 8, 10, 11, 12, 9, 7, 8]}
        ]
        
        print(f"Insertando datos de prueba para {municipio} {anio}...")
        
        inserted = 0
        for delito in delitos:
            for mes_idx, cantidad in enumerate(delito["cantidades"]):
                mes = mes_idx + 1
                fecha_hecho = date(anio, mes, 1)
                
                # Crear hash robusto
                hash_input = f"{municipio}|{depto}|{anio}|{mes}|{delito['tipo']}|seed_2025"
                registro_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                
                db_record = NationalCrimeStats(
                    departamento=depto,
                    municipio=municipio,
                    municipio_normalizado=municipio,
                    fecha_hecho=fecha_hecho,
                    anio=anio,
                    mes=mes,
                    tipo_delito=delito["tipo"],
                    cantidad=cantidad,
                    fuente_archivo="seed_2025_manual.xlsx",
                    hash_registro=registro_hash,
                    fecha_ingesta=datetime.utcnow()
                )
                
                # Usar una técnica de on conflict si no queremos duplicados
                # Pero aquí simplemente chequeamos si existe
                exists = db.query(NationalCrimeStats).filter(NationalCrimeStats.hash_registro == registro_hash).first()
                if not exists:
                    db.add(db_record)
                    inserted += 1
        
        db.commit()
        print(f"¡Se insertaron {inserted} registros de prueba para 2025 en Jamundí!")
        
    except Exception as e:
        print(f"Error en seeding de inteligencia: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_intelligence_2025()
