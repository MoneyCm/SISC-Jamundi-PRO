import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_portal_assets():
    print("Iniciando sesión como admin_sisc...")
    login_data = {"username": "admin_sisc", "password": "admin_password"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if resp.status_code != 200:
        print(f"Error login: {resp.status_code} - {resp.text}")
        return
        
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Consultando /api/mindefensa/assets...")
    resp = requests.get(f"{BASE_URL}/mindefensa/assets", headers=headers)
    
    if resp.status_code == 200:
        assets = resp.json()
        print(f"API RESPONDE: {len(assets)} activos encontrados.")
    else:
        print(f"ERROR API: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    test_portal_assets()
