import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_full_flow():
    print("1. Intentando Login...")
    # OAuth2PasswordRequestForm espera datos en formato form (data=...), no json=...
    login_data = {"username": "admin", "password": "admin_password"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if resp.status_code != 200:
        print(f"FAILED LOGIN: {resp.status_code} - {resp.text}")
        return
    
    token = resp.json()["access_token"]
    print(f"SUCCESS LOGIN. Token obtenido (len={len(token)})")

    print("\n2. Intentando obtener perfil (/me) con token...")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"ME RESP: {resp.status_code} - {resp.text}")

    print("\n3. Intentando Listar Usuarios con token...")
    resp = requests.get(f"{BASE_URL}/users/", headers=headers)
    print(f"USERS RESP: {resp.status_code} - (Total: {len(resp.json()) if resp.status_code == 200 else 'Error'})")

if __name__ == "__main__":
    test_full_flow()
