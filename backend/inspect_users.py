import sys
from sqlalchemy.orm import Session
from db.models import SessionLocal, User, Role

def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print("LISTADO DE USUARIOS (ASCII)")
        print("---------------------------")
        for user in users:
            role = db.query(Role).filter(Role.id == user.role_id).first()
            role_name = role.name if role else "SIN ROL"
            
            # Limpieza brutal de caracteres
            u_clean = ''.join(c for c in user.username if c.isprintable())
            r_clean = ''.join(c for c in role_name if c.isprintable())
            
            print(f"ID: {user.id} | User: {u_clean} | Role: {r_clean}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_users()
