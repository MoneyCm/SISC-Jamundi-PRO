import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- TOTAL DATOS POR FUENTE ---")
    query = """
        SELECT source_name, COUNT(*)
        FROM events
        GROUP BY source_name
    """
    res = conn.execute(text(query)).fetchall()
    for r in res:
        print(r)
