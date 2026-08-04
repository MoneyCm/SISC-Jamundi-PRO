from db.models import SessionLocal, User, Role
from core.security import verify_password
db = SessionLocal()
user = db.query(User).filter(User.username == "admin_sisc").first()
if user:
    pwd = "Jamundi2026"
    print(f"User: {user.username}")
    print(f"Password '{pwd}' check: {verify_password(pwd, user.password_hash)}")
else:
    print("User admin_sisc not found")
db.close()
