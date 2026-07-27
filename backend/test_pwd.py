from core.security import get_password_hash, verify_password
import bcrypt

pwd = "admin_password"
h = get_password_hash(pwd)
print(f"Hash: {h}")
print(f"Verify: {verify_password(pwd, h)}")
