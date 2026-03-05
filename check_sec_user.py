import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no encontrada.")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Buscar si ya existe
    result = conn.execute(text("SELECT id, username, email FROM users WHERE username = 'sec_seguridad'")).fetchone()
    if result:
        print(f"EXISTE: El usuario {result.username} (ID: {result.id}) ya existe con email {result.email}")
    else:
        print("NO_EXISTE: El usuario sec_seguridad no existe en la base de datos.")
