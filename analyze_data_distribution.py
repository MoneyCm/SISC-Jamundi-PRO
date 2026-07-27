import os
from sqlalchemy import create_engine, text

# DATABASE_URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- DISTRIBUCIÓN POR FUENTE (TOTAL) ---")
    res = conn.execute(text("SELECT source_name, COUNT(*) FROM events GROUP BY source_name")).fetchall()
    for r in res:
        print(f"Fuente: {r[0]} | Cantidad: {r[1]}")

    print("\n--- DISTRIBUCIÓN 2026 POR FUENTE ---")
    res = conn.execute(text("SELECT source_name, COUNT(*) FROM events WHERE occurrence_date >= '2026-01-01' GROUP BY source_name")).fetchall()
    for r in res:
        print(f"Fuente: {r[0]} | Cantidad: {r[1]}")

    print("\n--- DISTRIBUCIÓN 2025 POR FUENTE ---")
    res = conn.execute(text("SELECT source_name, COUNT(*) FROM events WHERE occurrence_date >= '2025-01-01' AND occurrence_date < '2026-01-01' GROUP BY source_name")).fetchall()
    for r in res:
        print(f"Fuente: {r[0]} | Cantidad: {r[1]}")

    print("\n--- TIPOS DE DELITOS (MINDEFENSA 2026) ---")
    # Usando ILIKE para evitar sensibilidad a mayúsculas/minúsculas
    res = conn.execute(text("SELECT descripcion, COUNT(*) FROM events WHERE source_name ILIKE 'MINDEFENSA%' AND occurrence_date >= '2026-01-01' GROUP BY descripcion")).fetchall()
    for r in res:
        print(f"Delito: {r[0]} | Cantidad: {r[1]}")
