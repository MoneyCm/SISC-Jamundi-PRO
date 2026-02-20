import os
from sqlalchemy import create_engine, text
import pandas as pd

def check_hom_stats():
    url = os.getenv("DATABASE_URL", "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(url)
    query = """
    SELECT 
        EXTRACT(YEAR FROM occurrence_date) as year,
        EXTRACT(MONTH FROM occurrence_date) as month,
        COUNT(*) as count
    FROM events e
    JOIN event_types et ON e.event_type_id = et.id
    WHERE et.category = 'HOMICIDIO'
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    
    try:
        with engine.connect() as conn:
            results = conn.execute(text(query)).fetchall()
            if not results:
                print("No se encontraron homicidios en la base de datos.")
            else:
                print("Estadísticas de Homicidios:")
                for r in results:
                    print(f"Año: {int(r.year)}, Mes: {int(r.month)}, Conteo: {r.count}")
    except Exception as e:
        print(f"Error consultando la base de datos: {e}")

if __name__ == "__main__":
    check_hom_stats()
