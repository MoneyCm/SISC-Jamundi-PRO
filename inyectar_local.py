import pandas as pd
from sqlalchemy import create_engine, text
import uuid
from datetime import datetime
from pathlib import Path

# URL Local (Docker)
LOCAL_URL = "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi"
DIR_DATA = Path(r"C:\Proyectos\monitor-mindefensa")

MAPEO = {
    "HOMICIDIO INTENCIONAL.xlsx": "HOMICIDIO INTENCIONAL",
    "SECUESTRO.xlsx": "SECUESTRO",
    "EXTORSIÓN.xlsx": "EXTORSIÓN",
    "HURTO PERSONAS.xlsx": "HURTO A PERSONAS",
    "HURTO A RESIDENCIAS.xlsx": "HURTO A RESIDENCIAS"
}

def inyectar_local():
    print("🚀 SINCRONIZANDO BASE DE DATOS LOCAL (Docker)")
    engine = create_engine(LOCAL_URL)
    
    with engine.connect() as conn:
        for file_name, label in MAPEO.items():
            path = DIR_DATA / file_name
            if not path.exists(): continue
            
            print(f"📦 Procesando {file_name}...", end="", flush=True)
            try:
                df = pd.read_excel(path, engine='openpyxl')
                df.columns = [str(c).upper().strip() for c in df.columns]
                df = df[pd.to_numeric(df['COD_MUNI'], errors='coerce') == 76364].copy()
                
                if df.empty:
                    print(" (Sin datos)")
                    continue

                success = 0
                for _, row in df.iterrows():
                    try:
                        fecha = pd.to_datetime(row.get('FECHA_HECHO') or row.get('FECHA')).date()
                        # Insertar una vez por cada unidad en 'CANTIDAD' o 'VICTIMAS'
                        cant = int(row.get('CANTIDAD', row.get('VICTIMAS', 1)))
                        for _ in range(max(1, cant)):
                            conn.execute(text("""
                                INSERT INTO events (id, external_id, occurrence_date, occurrence_time, barrio, estado, descripcion, source_name)
                                VALUES (:id, :ext, :f, :h, :b, :e, :d, :s)
                            """), {
                                "id": str(uuid.uuid4()), "ext": str(uuid.uuid4()), "f": fecha,
                                "h": datetime.strptime("00:00", "%H:%M").time(),
                                "b": str(row.get('MUNICIPIO', 'Jamundí')), "e": "ACTIVO",
                                "d": f"Local Sync: {label}", "s": "LOCAL_IMPORT"
                            })
                            success += 1
                    except: continue
                
                conn.commit()
                print(f" ✅ {success} registros locales.")
            except Exception as e:
                print(f" ❌ Error: {e}")

if __name__ == "__main__":
    inyectar_local()
