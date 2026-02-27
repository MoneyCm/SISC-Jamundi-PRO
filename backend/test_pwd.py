from core.security import get_password_hash, verify_password
import bcrypt

pwd = "admin_password"
h = get_password_hash(pwd)
print(f"Hash: {h}")
print(f"Verify: {verify_password(pwd, h)}")

# Test with a hardcoded hash that looks like what we have in init.sql
# admin123 hash from init.sql: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6L6s57RwRXWux.72
h_init = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6L6s57RwRXWux.72"
print(f"Verify admin123 from init.sql: {verify_password('admin123', h_init)}")
