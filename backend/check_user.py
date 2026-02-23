import sqlalchemy
from db.models import engine, User
from sqlalchemy.orm import Session

with Session(engine) as db:
    user = db.query(User).filter(User.username == "admin_sisc").first()
    if user:
        print(f"User FOUND: {user.username}, Role ID: {user.role_id}")
    else:
        print("User NOT FOUND")
