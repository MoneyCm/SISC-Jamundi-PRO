import sys, os
from sqlalchemy import create_engine
sys.path.append(os.path.abspath('backend'))
from db.models import Base
from db.models_auth import Role, User
from db.models_dq import DqReport, DqIssue
from db.models_intelligence import IntelligenceItem
from db.models_mindefensa import MinDefensaRecord
from db.models_policia import PoliciaRecord
from core.security import get_password_hash
from sqlalchemy.orm import sessionmaker

NEON_URL = "postgresql://neondb_owner:npg_5NY7BeOiHqoX@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

def init_neon():
    print("Iniciando Neon...")
    engine = create_engine(NEON_URL)
    Base.metadata.create_all(bind=engine)
    print("Tablas OK.")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(Role).first():
            admin_role = Role(name="Admin SISC", description="Administrador")
            db.add(admin_role)
            db.commit()
            if not db.query(User).filter(User.username == "admin").first():
                db.add(User(username="admin", email="admin@jamundi.gov.co", password_hash=get_password_hash("admin123"), role_id=admin_role.id, is_active=True))
                db.commit()
                print("Admin creado (admin123).")
        print("NEON LISTO")
    except Exception as e: print(f"Error: {e}")
    finally: db.close()

if __name__ == "__main__": init_neon()
