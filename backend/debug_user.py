import os
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
        test_password = os.getenv("SISC_TEST_PASSWORD")
        if test_password:
            print(f"Configured password check: {verify_password(test_password, user.password_hash)}")
    else:
        print(f"User '{username}' not found")

check_user("admin_sisc")
print("---")
check_user("admin")
db.close()
