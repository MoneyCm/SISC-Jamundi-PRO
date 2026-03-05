import sys, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.abspath('backend'))
from db.models_auth import User, Role
from core.security import get_password_hash

NEON_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5.us-east-1.aws.neon.tech/neondb?sslmode=require"

def fix():
    engine = create_engine(NEON_URL)
    db = sessionmaker(bind=engine)()
    try:
        u = db.query(User).filter(User.username == "admin_sisc").first()
        if u:
            u.password_hash = get_password_hash("Jamundi2026")
            db.commit()
            print("✅ LOGIN SISC RESET: Jamundi2026")
        else:
            print("❌ Usuario no encontrado")
    except Exception as e: print(f"Error: {e}")
    finally: db.close()
if __name__ == "__main__": fix()
