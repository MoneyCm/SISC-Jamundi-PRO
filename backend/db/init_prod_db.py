import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure paths work (add 'backend' root to path)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

from db.models import Base, Event, EventType, Role, User
from core.security import get_password_hash

def seed_production(db_url):
    print(f"Iniciando siembra en: {db_url.split('@')[-1]} (ocultando credenciales)")
    
    # Fix for SQLAlchemy
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        print("Tablas creadas correctamente.")

        # 1. Roles
        roles_data = [
            {"name": "Admin SISC", "description": "Administrador total del sistema"},
            {"name": "Analista Observatorio", "description": "Usuario técnico para análisis y boletines"}
        ]
        
        for r_data in roles_data:
            role = db.query(Role).filter(Role.name == r_data["name"]).first()
            if not role:
                db.add(Role(name=r_data["name"], description=r_data["description"]))
        
        db.commit()
        admin_role = db.query(Role).filter(Role.name == "Admin SISC").first()

        # 2. Admin User
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            db.add(User(
                username="admin",
                email="admin@jamundi.gov.co",
                password_hash=get_password_hash("admin123"), # Cambiar después
                role_id=admin_role.id,
                is_active=True
            ))
            print("Usuario 'admin' (pass: admin123) creado.")

        db.commit()
        print("¡Base de datos inicializada con éxito!")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    url = input("Pega tu DATABASE_URL de Render aquí: ")
    if url:
        seed_production(url)
