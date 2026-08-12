from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Limpiando datos de POLICIA_SEMANAL para reinicio limpio...")
    
    # 1. Obtener IDs de IngestionRuns de esta fuente
    run_ids = conn.execute(text("SELECT id FROM ingestion_runs WHERE fuente_codigo = 'POLICIA_SEMANAL'")).fetchall()
    ids_tuple = tuple(str(r[0]) for r in run_ids)
    
    # Borrar Eventos (filtrando por source_name para estar seguros de borrar los huérfanos también)
    conn.execute(text("DELETE FROM events WHERE source_name LIKE 'POLICIA_SEMANAL%'"))
    
    # Borrar Hechos
    conn.execute(text("DELETE FROM hechos_seguridad WHERE fuente_codigo = 'POLICIA_SEMANAL'"))
    
    if ids_tuple:
        # Borrar Issues
        conn.execute(text("DELETE FROM ingestion_issues WHERE ingestion_id IN :ids"), {"ids": ids_tuple})
        
        # Borrar Staging
        conn.execute(text("DELETE FROM stg_policia_semanal WHERE ingestion_id IN :ids"), {"ids": ids_tuple})
        
        # Borrar Runs
        conn.execute(text("DELETE FROM ingestion_runs WHERE fuente_codigo = 'POLICIA_SEMANAL'"))
    
    conn.commit()
    print("Limpieza completada. La base de datos está lista para una carga limpia.")



