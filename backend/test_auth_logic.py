import requests
import json

BASE_URL = "http://localhost:8000"

def test_full_flow():
    print("1. Intentando Login...")
    login_data = {"username": "admin", "password": "admin123"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if resp.status_code != 200:
        print(f"FAILED LOGIN: {resp.status_code} - {resp.text}")
        return
    
    token = resp.json()["access_token"]
    print(f"SUCCESS LOGIN. Token obtenido (len={len(token)})")

    print("\n2. Intentando Bulk Upload con token...")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = [
        {
            "fecha": "2024-01-01",
            "hora": "10:00",
            "tipo": "HOMICIDIO",
            "barrio": "TEST BARRIO",
            "latitud": 3.26,
            "longitud": -76.53
        }
    ]
    resp = requests.post(f"{BASE_URL}/ingesta/bulk", headers=headers, json=payload)
    print(f"BULK RESP: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    test_full_flow()
