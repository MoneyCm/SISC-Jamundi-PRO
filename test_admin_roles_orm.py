import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models_auth import User, Role, UserRole

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

print("--- ROLES DEL ADMIN SISC ---")
admin = db.query(User).filter(User.username.like('%admin%')).first()
if admin:
    print(f"User: {admin.username} | id: {admin.id}")
    for role in admin.roles:
        print(f"- Role: {role.code} ({role.name})")

    if len(admin.roles) == 0:
        print("No tiene roles asginados.")
else:
    print("User admin not found.")
