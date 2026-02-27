import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_executive_brief():
    login_data = {"username": "admin_sisc", "password": "admin_password"}
    resp = requests.post(BASE_URL + "/auth/login", data=login_data)
    if resp.status_code != 200:
        print("Login Error")
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}

    print("Requesting executive-brief...")
    resp = requests.get(BASE_URL + "/intelligence/executive-brief", headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        print("Success. Items found:", len(data))
        for item in data:
            print("--- " + str(item['delito']) + " ---")
            print("Corte: " + str(item['fecha_corte']))
            print("IA: " + str(item['analisis_ia']))
    else:
        print("Error:", resp.status_code)

if __name__ == "__main__":
    test_executive_brief()
