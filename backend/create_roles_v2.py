from sqlalchemy.orm import Session
from db.models import SessionLocal, Role, User, engine, Base
from core.security import get_password_hash
import sys

def init_db():
    print("🚀 Iniciando script de creación de usuarios...")
    db = SessionLocal()
    try:
        # 1. Crear Roles
        roles_data = [
            {"name": "Analista Institucional", "description": "Acceso total a datos, reportes y mapas sin censura."},
            {"name": "Tomador de Decisiones (Ejecutivo)", "description": "Acceso a dashboards estratégicos y alertas."},
            {"name": "Enlace Fuerza Pública", "description": "Acceso a mapa táctico operativo."},
            {"name": "Administrador (Observatorio)", "description": "Control total del sistema."}
        ]

        print("--- Creando Roles ---")
        role_map = {}
        for r_data in roles_data:
            role = db.query(Role).filter(Role.name == r_data["name"]).first()
            if not role:
                print(f"➕ Creando nuevo rol: {r_data['name']}")
                role = Role(name=r_data["name"], description=r_data["description"])
                db.add(role)
                db.commit() # Commit parcial para asegurar disponibilidad
                db.refresh(role)
            else:
                print(f"ℹ️ Rol existente: {r_data['name']} (ID: {role.id})")
            
            role_map[r_data["name"]] = role.id

        # 2. Crear Usuarios Demo
        users_data = [
            {"username": "analista_demo", "email": "analista@jamundi.gov.co", "password": "sisc_analista", "role": "Analista Institucional"},
            {"username": "ejecutivo_demo", "email": "despacho@jamundi.gov.co", "password": "sisc_ejecutivo", "role": "Tomador de Decisiones (Ejecutivo)"},
            {"username": "policia_demo", "email": "comandante@policia.gov.co", "password": "sisc_policia", "role": "Enlace Fuerza Pública"},
            {"username": "admin_sisc", "email": "admin@sisc.gov.co", "password": "admin_password", "role": "Administrador (Observatorio)"}
        ]

        print("\n--- Creando Usuarios ---")
        for u_data in users_data:
            user = db.query(User).filter(User.username == u_data["username"]).first()
            if not user:
                role_id = role_map.get(u_data["role"])
                if role_id:
                    print(f"➕ Creando usuario: {u_data['username']} para rol ID {role_id}")
                    hashed_pwd = get_password_hash(u_data["password"])
                    new_user = User(
                        username=u_data["username"],
                        email=u_data["email"],
                        password_hash=hashed_pwd,
                        role_id=role_id,
                        is_active=True
                    )
                    db.add(new_user)
                else:
                    print(f"❌ Error crítico: Rol '{u_data['role']}' no encontrado en el mapa para usuario {u_data['username']}")
            else:
                print(f"ℹ️ Usuario existente: {u_data['username']}")
        
        db.commit()
        print("\n✅ ¡Inicialización de Roles y Usuarios completada con éxito!")

    except Exception as e:
        print(f"❌ Error fatal durante la inicialización: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
