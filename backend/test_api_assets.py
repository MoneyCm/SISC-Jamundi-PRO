import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_get_assets():
    # 1. Login para obtener token
    print("Iniciando sesión como admin...")
    login_data = {"username": "admin", "password": "admin_password"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if resp.status_code != 200:
        print(f"Error login: {resp.status_code} - {resp.text}")
        return
        
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Consultar assets
    print("Consultando activos de MinDefensa...")
    resp = requests.get(f"{BASE_URL}/mindefensa/assets", headers=headers)
    
    if resp.status_code == 200:
        assets = resp.json()
        print(f"Éxito. Encontrados {len(assets)} activos en el API.")
        if len(assets) > 0:
            print(f"Ejemplo: {assets[0]['dataset_code']} - Status: {assets[0]['status']}")
    else:
        print(f"Error API: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    # Asegurémonos que el servidor esté corriendo antes de ejecutar
    test_get_assets()
