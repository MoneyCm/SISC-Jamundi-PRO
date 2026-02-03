from sqlalchemy import create_engine, text
import os
import sys

# Añadir el directorio actual al path para que las importaciones funcionen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import SQLALCHEMY_DATABASE_URL

def migrate():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    with engine.connect() as conn:
        print("Verificando y agregando columnas faltantes a la tabla 'events'...")
        
        # Agregar barrio
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN barrio VARCHAR(100);"))
            print("- Columna 'barrio' agregada.")
        except Exception as e:
            if "already exists" in str(e):
                print("- Columna 'barrio' ya existía.")
            else:
                print(f"- Error agregando 'barrio': {e}")
        
        # Agregar estado
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN estado VARCHAR(50) DEFAULT 'Abierto';"))
            print("- Columna 'estado' agregada.")
        except Exception as e:
            if "already exists" in str(e):
                print("- Columna 'estado' ya existía.")
            else:
                print(f"- Error agregando 'estado': {e}")
                
        # Agregar descripcion
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN descripcion TEXT;"))
            print("- Columna 'descripcion' agregada.")
        except Exception as e:
            if "already exists" in str(e):
                print("- Columna 'descripcion' ya existía.")
            else:
                print(f"- Error agregando 'descripcion': {e}")
        
        conn.commit()
        print("¡Migración completada!")

if __name__ == "__main__":
    migrate()
