import os
from sqlalchemy import create_engine, text

# DATABASE_URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- DISTRIBUCIÓN POR AÑO (MINDEFENSA_SYNC) ---")
    res = conn.execute(text("SELECT EXTRACT(YEAR FROM occurrence_date) as anio, COUNT(*) FROM events WHERE source_name = 'MINDEFENSA_SYNC' GROUP BY anio ORDER BY anio DESC")).fetchall()
    for r in res:
        print(f"Año: {r[0]} | Cantidad: {r[1]}")

    print("\n--- OTRAS FUENTES NO MINDEFENSA ---")
    res = conn.execute(text("SELECT source_name, COUNT(*) FROM events WHERE source_name NOT ILIKE 'MINDEFENSA%' GROUP BY source_name")).fetchall()
    for r in res:
        print(f"Fuente: {r[0]} | Cantidad: {r[1]}")
