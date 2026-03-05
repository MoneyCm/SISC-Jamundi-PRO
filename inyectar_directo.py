import pandas as pd
from sqlalchemy import create_engine, text
import uuid
from datetime import datetime
from pathlib import Path

NEON_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
DIR_DATA = Path(r"C:\Proyectos\monitor-mindefensa")

MAPEO = {
    "HOMICIDIO INTENCIONAL.xlsx": "HOMICIDIO INTENCIONAL",
    "SECUESTRO.xlsx": "SECUESTRO",
    "EXTORSIÓN.xlsx": "EXTORSIÓN",
    "HURTO PERSONAS.xlsx": "HURTO A PERSONAS",
    "HURTO A RESIDENCIAS.xlsx": "HURTO A RESIDENCIAS",
    "HURTO DE VEHÍCULOS.xlsx": "HURTO DE VEHÍCULOS",
    "HURTO A COMERCIO.xlsx": "HURTO A COMERCIO",
    "LESIONES COMUNES.xlsx": "LESIONES COMUNES",
    "VIOLENCIA INTRAFAMILIAR.xlsx": "VIOLENCIA INTRAFAMILIAR",
    "DELITOS SEXUALES.xlsx": "DELITOS_SEXUALES",
    "TERRORISMO.xlsx": "TERRORISMO",
    "MASACRES.xlsx": "MASACRES"
}

def inyectar():
    print("🚀 INYECTOR NEON v2")
    engine = create_engine(NEON_URL)
    
    with engine.connect() as conn:
        for file_name, label in MAPEO.items():
            path = DIR_DATA / file_name
            if not path.exists(): continue
            
            print(f"📦 {file_name}...", end="", flush=True)
            try:
                df = pd.read_excel(path, engine='openpyxl')
                df.columns = [str(c).upper().strip() for c in df.columns]
                df = df[df['COD_MUNI'] == 76364].copy()
                
                if df.empty:
                    print(" (Sin datos)")
                    continue

                # Inyectar uno por uno para respetar el esquema complejo del SISC
                success = 0
                for _, row in df.iterrows():
                    try:
                        fecha = pd.to_datetime(row.get('FECHA_HECHO') or row.get('FECHA')).date()
                        conn.execute(text("""
                            INSERT INTO events (id, external_id, occurrence_date, occurrence_time, barrio, estado, descripcion, source_name)
                            VALUES (:id, :ext, :f, :h, :b, :e, :d, :s)
                            ON CONFLICT DO NOTHING
                        """), {
                            "id": str(uuid.uuid4()), "ext": str(uuid.uuid4()), "f": fecha,
                            "h": datetime.strptime("00:00", "%H:%M").time(),
                            "b": str(row.get('MUNICIPIO', 'Jamundí')), "e": "ACTIVO",
                            "d": f"Carga Directa: {label}", "s": "MINDEFENSA_SYNC"
                        })
                        success += 1
                    except: continue
                
                conn.commit()
                print(f" ✅ {success} registros.")
            except Exception as e:
                print(f" ❌ Error: {e}")

if __name__ == "__main__":
    inyectar()
