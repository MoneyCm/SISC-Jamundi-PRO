from sqlalchemy.orm import Session
from db.models import SessionLocal, Role, User, engine, Base, create_tables
from core.security import get_password_hash
import uuid

def fix_prod_db():
    print("--- INICIANDO REPARACIÓN DE BD PRODUCCIÓN ---")
    
    # 1. Asegurar tablas
    print("Verificando tablas...")
    create_tables()
    
    db = SessionLocal()
    try:
        # 2. Asegurar Roles base
        role_codes = ["TI_ADMIN", "FUNC_ADMIN", "ANALYST", "DATA_OWNER", "VIEWER"]
        for code in role_codes:
            exists = db.query(Role).filter(Role.code == code).first()
            if not exists:
                print(f"Creando rol: {code}")
                new_role = Role(id=uuid.uuid4(), code=code, name=code.replace("_", " ").title())
                db.add(new_role)
        
        db.commit()
        
        # 3. Asegurar Usuario admin_sisc
        admin_role = db.query(Role).filter(Role.code == "TI_ADMIN").first()
        user = db.query(User).filter(User.username == "admin_sisc").first()
        
        if not user:
            print("Creando usuario admin_sisc en producción...")
            new_user = User(
                id=uuid.uuid4(),
                username="admin_sisc",
                hashed_password=get_password_hash("admin_password"),
                full_name="Administrador SISC Jamundí",
                role_id=admin_role.id,
                is_active=True,
                data_level_max=3
            )
            db.add(new_user)
            print("✅ Usuario creado con éxito.")
        else:
            print(f"ℹ️ Usuario admin_sisc ya existe. Actualizando contraseña...")
            user.hashed_password = get_password_hash("admin_password")
            user.is_active = True
            user.role_id = admin_role.id
            print("✅ Credenciales actualizadas.")
            
        db.commit()
        print("--- PROCESO COMPLETADO ---")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_prod_db()
