import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SessionLocal
from db.models import User
from core.security import get_password_hash

def reset_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("Reseteando password de admin...")
            admin.password_hash = get_password_hash("admin_password")
            db.commit()
            print("¡Éxito!")
        else:
            print("Usuario admin no encontrado.")
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()
