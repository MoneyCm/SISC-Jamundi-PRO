import sys, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.abspath('backend'))
from db.models_auth import User
from core.security import get_password_hash

# URL Local (Docker)
LOCAL_URL = "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi"

def fix_local():
    print("Conectando a Docker Local...")
    try:
        engine = create_engine(LOCAL_URL)
        db = sessionmaker(bind=engine)()
        u = db.query(User).filter(User.username == "admin_sisc").first()
        if u:
            u.password_hash = get_password_hash("Jamundi2026")
            db.commit()
            print("✅ CONTRASEÑA LOCAL ACTUALIZADA: Jamundi2026")
        else:
            print("❌ No se encontró el usuario local admin_sisc")
        db.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__": fix_local()
