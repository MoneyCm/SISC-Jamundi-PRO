import sys, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.abspath('backend'))
from db.models_auth import User
from core.security import get_password_hash

# URL exacta del pooler proporcionada por el usuario
NEON_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

def fix():
    print(f"Conectando a Neon (Pooler)...")
    try:
        engine = create_engine(NEON_URL)
        Session = sessionmaker(bind=engine)
        db = Session()
        u = db.query(User).filter(User.username == "admin_sisc").first()
        if u:
            u.password_hash = get_password_hash("Jamundi2026")
            db.commit()
            print("✅ CLAVE ACTUALIZADA: Jamundi2026")
        else:
            print("❌ Usuario 'admin_sisc' no encontrado en la base de datos.")
        db.close()
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    fix()
