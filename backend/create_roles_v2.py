from sqlalchemy.orm import Session
from db.models import SessionLocal, Role, User, engine, Base
from db.models_auth import Permission
from core.security import get_password_hash
import sys
import uuid

def init_db():
    print("🚀 Iniciando script de creación de sistema institucional de usuarios...")
    db = SessionLocal()
    try:
        # 1. Crear Roles según especificación
        roles_data = [
            {"code": "TI_ADMIN", "name": "Administrador TI", "description": "Control total técnico, gestión de seguridad y auditoría."},
            {"code": "FUNC_ADMIN", "name": "Administrador Funcional", "description": "Gestión de usuarios N1/N2 y roles de negocio."},
            {"code": "DATA_OWNER", "name": "Dueño de Datos", "description": "Aprobadador final de acceso a datos restringidos (N3)."},
            {"code": "STEWARD", "name": "Custodio de Datos", "description": "Administra catálogo, calidad y anonimización."},
            {"code": "ANALYST", "name": "Analista Profesional", "description": "Acceso a datos institucionales (N2) para analítica avanzada."},
            {"code": "DIRECTIVE", "name": "Directivo / Secretario", "description": "Acceso a dashboards estratégicos y alertas."},
            {"code": "SOURCE_UPLOADER", "name": "Cargador de Fuentes", "description": "Permiso para subir archivos a la plataforma."},
            {"code": "PORTAL_EDITOR", "name": "Editor de Portal", "description": "Edita boletines y contenido público."},
            {"code": "PORTAL_ADMIN", "name": "Admin de Portal", "description": "Publica y gestiona el Portal Ciudadano."}
        ]

        print("--- Creando/Actualizando Roles ---")
        role_map = {}
        for r_data in roles_data:
            role = db.query(Role).filter(Role.code == r_data["code"]).first()
            if not role:
                print(f"➕ Creando nuevo rol: {r_data['name']} ({r_data['code']})")
                role = Role(code=r_data["code"], name=r_data["name"], description=r_data["description"])
                db.add(role)
                db.commit()
                db.refresh(role)
            else:
                print(f"ℹ️ Rol existente: {r_data['code']}")
            role_map[r_data["code"]] = role

        # 2. Crear Administrador Inicial
        admin_data = {
            "username": "admin_sisc",
            "email": "admin@jamundi.gov.co",
            "password": "admin_password", # Cambiar en primera sesión
            "full_name": "Administrador de Sistema SISC",
            "role_codes": ["TI_ADMIN", "FUNC_ADMIN", "DATA_OWNER"],
            "data_level_max": 3
        }

        print("\n--- Verificando Superusuario ---")
        # Buscar por username O por email (para migración admin -> admin_sisc)
        admin_user = db.query(User).filter(
            (User.username == admin_data["username"]) | 
            (User.email == admin_data["email"])
        ).first()
        
        if not admin_user:
            print(f"➕ Creando superusuario: {admin_data['username']}")
            hashed_pwd = get_password_hash(admin_data["password"])
            admin_user = User(
                username=admin_data["username"],
                email=admin_data["email"],
                password_hash=hashed_pwd,
                full_name=admin_data["full_name"],
                data_level_max=admin_data["data_level_max"],
                is_active=True
            )
            db.add(admin_user)
            db.flush()
        else:
            print(f"ℹ️ Superusuario encontrado (ID: {admin_user.id}). Asegurando credenciales...")
            # Forzar username a admin_sisc si era diferente (Migración)
            if admin_user.username != admin_data["username"]:
                print(f"🔄 Migrando username: {admin_user.username} -> {admin_data['username']}")
                admin_user.username = admin_data["username"]
            
            # Asegurar contraseña correcta (admin_password)
            admin_user.password_hash = get_password_hash(admin_data["password"])
            admin_user.is_active = True
            db.flush()
            
        # Asignar roles (común para creación y update)
        current_role_codes = [r.code for r in admin_user.roles]
        for code in admin_data["role_codes"]:
            if code not in current_role_codes:
                role = role_map.get(code)
                if role:
                    admin_user.roles.append(role)
                    print(f"➕ Rol {code} asignado a {admin_user.username}")
        
        db.commit()

        print("\n✅ ¡Inicialización completada con éxito!")

    except Exception as e:
        print(f"❌ Error fatal durante la inicialización: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
