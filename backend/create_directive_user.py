from sqlalchemy.orm import Session
from db.models import SessionLocal, Role, User
from core.security import get_password_hash
import sys

def create_directive():
    print("--- Creando usuario de prueba: Secretario de Seguridad ---")
    db = SessionLocal()
    try:
        # 1. Datos del usuario
        username = "secretario_seguridad"
        email = "secretario@jamundi.gov.co"
        password = "secretario123"
        full_name = "Secretario de Seguridad Jamundí"
        
        # 2. Verificar si ya existe
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"Info: El usuario '{username}' ya existe. Actualizando contraseña...")
            user.password_hash = get_password_hash(password)
        else:
            print(f"Creando nuevo usuario: {username}")
            user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                full_name=full_name,
                data_level_max=2, # Nivel Institucional
                is_active=True
            )
            db.add(user)
        
        db.flush()

        # 3. Asignar Rol DIRECTIVE
        directive_role = db.query(Role).filter(Role.code == "DIRECTIVE").first()
        if not directive_role:
            print("Error: El rol 'DIRECTIVE' no existe en la base de datos. Ejecute primero create_roles_v2.py")
            return

        if directive_role not in user.roles:
            user.roles.append(directive_role)
            print(f"Rol 'DIRECTIVE' asignado a {username}")

        db.commit()
        print(f"\nUsuario creado con éxito:")
        print(f"   Usuario: {username}")
        print(f"   Clave: {password}")
        print(f"   Nivel Datos: 2 (Institucional)")

    except Exception as e:
        print(f"❌ Error during creation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_directive()
