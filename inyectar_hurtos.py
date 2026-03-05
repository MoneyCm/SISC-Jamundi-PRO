import pandas as pd
from sqlalchemy import create_engine, text
import uuid
from datetime import datetime
from pathlib import Path

NEON_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
FILE_PATH = r"C:\Proyectos\monitor-mindefensa\HURTO PERSONAS.xlsx"

def inyectar_hurtos():
    print(f"🚀 Iniciando rescate de Hurto a Personas para Jamundí...")
    engine = create_engine(NEON_URL)
    
    try:
        # Cargar solo columnas necesarias para ahorrar memoria
        df = pd.read_excel(FILE_PATH, engine='openpyxl', usecols=['FECHA_HECHO', 'COD_MUNI', 'MUNICIPIO', 'CANTIDAD'])
        
        # Filtrar por código de Jamundí (forzando a número)
        df['COD_MUNI'] = pd.to_numeric(df['COD_MUNI'], errors='coerce')
        df_jamundi = df[df['COD_MUNI'] == 76364].copy()
        
        if df_jamundi.empty:
            print("⚠️ No se encontraron registros de Jamundí en este archivo.")
            return

        print(f"✅ Encontrados {len(df_jamundi)} registros. Inyectando...")

        with engine.connect() as conn:
            for _, row in df_jamundi.iterrows():
                try:
                    fecha = pd.to_datetime(row['FECHA_HECHO']).date()
                    cantidad = int(row['CANTIDAD'])
                    
                    # Insertar una fila por cada unidad en 'CANTIDAD' para mantener consistencia con el SISC
                    for _ in range(cantidad):
                        conn.execute(text("""
                            INSERT INTO events (id, external_id, occurrence_date, occurrence_time, barrio, estado, descripcion, source_name)
                            VALUES (:id, :ext, :f, :h, :b, :e, :d, :s)
                        """), {
                            "id": str(uuid.uuid4()), 
                            "ext": str(uuid.uuid4()), 
                            "f": fecha,
                            "h": datetime.strptime("00:00", "%H:%M").time(),
                            "b": str(row['MUNICIPIO']), 
                            "e": "ACTIVO",
                            "d": "Carga Directa: HURTO A PERSONAS", 
                            "s": "MINDEFENSA_SYNC"
                        })
                except: continue
            conn.commit()
        print("🎉 Hurto a Personas sincronizado exitosamente.")

    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    inyectar_hurtos()
