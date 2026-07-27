
import requests
import os

db_url = os.getenv("DATABASE_URL")
API_URL = "http://localhost:8000/api/auth/login"

def check_api():
    # 1. Login
    res = requests.post(API_URL, data={"username": "admin_sisc", "password": "Jamundi2026"})
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
        return

    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Check expedientes
    res = requests.get("http://localhost:8000/api/inspecciones/expedientes", headers=headers)
    print(f"Expedientes status: {res.status_code}")
    print(f"Expedientes data: {res.text[:500]}") # First 500 chars

    # 3. Check stats
    res = requests.get("http://localhost:8000/api/inspecciones/stats/summary", headers=headers)
    print(f"Stats status: {res.status_code}")
    print(f"Stats data: {res.json()}")

if __name__ == "__main__":
    check_api()
