import requests
import sys

BASE_URL = "http://localhost:8000"

def test_auth():
    print("--- Probando Flujo de Autenticación SISC Jamundí ---")
    
    # 1. Intentar login con credenciales correctas
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print(f"\n1. Intentando login con {login_data['username']}...")
    try:
        response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("[OK] Login exitoso. Token recibido.")
        else:
            print(f"[ERROR] Falló el login: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"[ERROR] No se pudo conectar al servidor: {e}")
        print("\n¿Asegúrate de que el backend esté corriendo en el puerto 8000?")
        return

    # 2. Probar acceso a /auth/me con el token
    print("\n2. Verificando identidad en /auth/me...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if response.status_code == 200:
        user_info = response.json()
        print(f"[OK] Usuario autenticado: {user_info['username']} ({user_info['email']})")
    else:
        print(f"[ERROR] Falló la verificación: {response.status_code} - {response.text}")

    # 3. Probar login fallido
    print("\n3. Probando login con contraseña incorrecta...")
    bad_login = {"username": "admin", "password": "wrongpassword"}
    response = requests.post(f"{BASE_URL}/auth/login", data=bad_login)
    if response.status_code == 401:
        print("[OK] Acceso denegado correctamente.")
    else:
        print(f"[ALERTA] Se esperaba 401 pero se obtuvo {response.status_code}")

if __name__ == "__main__":
    test_auth()
