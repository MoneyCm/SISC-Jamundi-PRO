from db.models import SessionLocal, User, Role
db = SessionLocal()
def check_user(username):
    user = db.query(User).filter(User.username == username).first()
    if user:
        print(f"User found: {user.username}")
        print(f"Email: {user.email}")
        print(f"Is active: {user.is_active}")
        print(f"Roles: {[r.code for r in user.roles]}")
        from core.security import verify_password
        print(f"Password 'admin_password' check: {verify_password('admin_password', user.password_hash)}")
        print(f"Password 'admin123' check: {verify_password('admin123', user.password_hash)}")
    else:
        print(f"User '{username}' not found")

check_user("admin_sisc")
print("---")
check_user("admin")
db.close()
