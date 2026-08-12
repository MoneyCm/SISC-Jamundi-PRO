from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- ULTIMOS 10 EVENTOS POLICIA_SEMANAL ---")
    res = conn.execute(text("SELECT id, source_name, descripcion, occurrence_date FROM events WHERE source_name LIKE 'POLICIA_SEMANAL%' ORDER BY id DESC LIMIT 10")).fetchall()
    for row in res:
        print(f"ID: {row[0]} | Source: {row[1]} | Desc: {row[2]}")

    print("\n--- CONTEO POR DESCRIPCION ---")
    res = conn.execute(text("SELECT descripcion, count(*) FROM events WHERE source_name LIKE 'POLICIA_SEMANAL%' GROUP BY descripcion ORDER BY count(*) DESC LIMIT 20")).fetchall()
    for row in res:
        print(f"{row[0]}: {row[1]}")



