from sqlalchemy.orm import Session
from db.models import SessionLocal, User
from core.security import verify_password, get_password_hash

def check_login(username, password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ Usuario '{username}' NO encontrado en la base de datos.")
            return

        print(f"✅ Usuario '{username}' encontrado. ID: {user.id}")
        print(f"🔑 Hash almacenado: {user.password_hash}")
        
        # Prueba 1: Verificar con la función del sistema
        is_valid = verify_password(password, user.password_hash)
        print(f"🔍 Resultado de verify_password('{password}'): {is_valid}")

        # Prueba 2: Generar nuevo hash y comparar
        new_hash = get_password_hash(password)
        print(f"🆕 Nuevo hash generado para referencia: {new_hash}")
        
        if is_valid:
            print("🎉 ¡La contraseña es CORRECTA según el sistema!")
        else:
            print("⚠️ La contraseña es INCORRECTA. Posible problema de salt o codificación.")

    finally:
        db.close()

if __name__ == "__main__":
    check_login("analista_demo", "sisc_analista")
