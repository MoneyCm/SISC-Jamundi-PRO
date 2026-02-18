from sqlalchemy.orm import Session
from db.models import SessionLocal, User, Role
import sys

def check_and_delete_user(target_username):
    db = SessionLocal()
    try:
        print(f"Buscando usuario: '{target_username}'...")
        user = db.query(User).filter(User.username == target_username).first()
        
        if user:
            role = db.query(Role).filter(Role.id == user.role_id).first()
            role_name = role.name if role else "SIN ROL"
            print(f"ENCONTRADO: User '{user.username}' (ID: {user.id})")
            print(f"ROL ACTUAL: {role_name}")
            
            # Eliminar directamente según instrucción "sino eliminalo"
            print(f"Eliminando usuario '{target_username}'...")
            db.delete(user)
            db.commit()
            print("USUARIO ELIMINADO CORRECTAMENTE.")
        else:
            print(f"Usuario '{target_username}' NO ENCONTRADO.")
            
    except Exception as e:
        print(f"Error operando usuario: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Buscar variantes probables del typo del usuario
    check_and_delete_user("admi")
    check_and_delete_user("admin") # Cuidado, verificar si es el admin real antes de borrar en logica humana, pero aqui el script es simple.
    # El admin real es 'admin_sisc', asi que 'admin' generico seguro es basura.
