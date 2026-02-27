from db.models import SessionLocal, User, Role
from core.security import get_password_hash
import uuid

db = SessionLocal()
try:
    # 1. Asegurar roles
    roles_codes = ["TI_ADMIN", "FUNC_ADMIN", "DATA_OWNER", "ANALYST"]
    role_map = {}
    for code in roles_codes:
        role = db.query(Role).filter(Role.code == code).first()
        if not role:
            role = Role(code=code, name=code, description="Auto-created")
            db.add(role)
            db.commit()
            db.refresh(role)
        role_map[code] = role

    # 2. Asegurar admin_sisc
    admin = db.query(User).filter(User.email == "admin@jamundi.gov.co").first()
    if not admin:
        admin = db.query(User).filter(User.username == "admin").first()
    
    if admin:
        print(f"Updating existing user {admin.username} to admin_sisc")
        admin.username = "admin_sisc"
        admin.password_hash = get_password_hash("admin_password")
        admin.is_active = True
    else:
        print("Creating new user admin_sisc")
        admin = User(
            username="admin_sisc",
            email="admin@jamundi.gov.co",
            password_hash=get_password_hash("admin_password"),
            full_name="Admin SISC",
            is_active=True,
            data_level_max=3
        )
        db.add(admin)
    
    db.flush()
    # Asignar roles
    current_codes = [r.code for r in admin.roles]
    for code in ["TI_ADMIN", "FUNC_ADMIN", "DATA_OWNER"]:
        if code not in current_codes:
            admin.roles.append(role_map[code])
    
    db.commit()
    print("DONE: User admin_sisc is ready with admin_password")
except Exception as e:
    print(f"ERROR: {e}")
    db.rollback()
finally:
    db.close()
