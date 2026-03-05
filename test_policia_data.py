from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
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
