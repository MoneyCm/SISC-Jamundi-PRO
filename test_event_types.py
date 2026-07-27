import os
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- Eventos de 2026 (MINDEFENSA) ---")
    query = """
        SELECT e.id, e.descripcion, e.event_type_id, et.category
        FROM events e
        LEFT JOIN event_types et ON e.event_type_id = et.id
        WHERE e.source_name LIKE 'MINDEFENSA%'
        AND e.occurrence_date >= '2026-01-01'
        LIMIT 5
    """
    res = conn.execute(text(query)).fetchall()
    for r in res:
        print(r)
