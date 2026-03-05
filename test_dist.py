from sqlalchemy import create_engine, text
from datetime import date
import os
from dotenv import load_dotenv

DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- Test API query para MINDEFENSA en 2026 ---")
    query = """
        SELECT descripcion as category, count(id) as total 
        FROM events 
        WHERE source_name LIKE 'MINDEFENSA%' 
        AND occurrence_date >= '2026-01-01' 
        AND occurrence_date <= '2026-03-05' 
        GROUP BY descripcion
    """
    res = conn.execute(text(query)).fetchall()
    print("Resultados 2026:", res)
    
    print("\n--- Test API query para MINDEFENSA en 2025 ---")
    query2 = """
        SELECT descripcion as category, count(id) as total 
        FROM events 
        WHERE source_name LIKE 'MINDEFENSA%' 
        AND occurrence_date >= '2025-01-01' 
        GROUP BY descripcion
    """
    res2 = conn.execute(text(query2)).fetchall()
    print("Resultados > 2025:", len(res2), "filas encontradas.")
