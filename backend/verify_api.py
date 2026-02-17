import urllib.request
import urllib.parse
import json

def test():
    print("--- INICIANDO VERIFICACIÓN DE API ---")
    try:
        # 1. Test Login
        login_url = "http://localhost:8000/auth/login"
        login_data = urllib.parse.urlencode({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(login_url, data=login_data)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            token = res['access_token']
            print(f"PASS: Login exitoso. Token obtenido.")
        
        # 2. Test Bulk (Authorization Header)
        bulk_url = "http://localhost:8000/ingesta/bulk"
        payload = json.dumps([{
            "fecha": "2024-01-01",
            "hora": "12:00",
            "tipo": "HOMICIDIO",
            "barrio": "VERIFICACION_TECNICA",
            "latitud": 3.26,
            "longitud": -76.53
        }]).encode()
        
        req = urllib.request.Request(bulk_url, data=payload, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as response:
            print(f"PASS: Bulk upload exitoso. Status: {response.status}")
            print(f"Respuesta Servidor: {response.read().decode()}")

    except Exception as e:
        print(f"FAIL: Error en la verificación: {e}")

if __name__ == "__main__":
    test()
