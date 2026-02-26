import pandas as pd
import hashlib
import requests
import os
import sys

def get_source_id(name):
    name = name.upper()
    if 'ASPERSION' in name: return 'ASPERSION'
    if 'AFECTACIÓN' in name or 'FUERZA PÚBLICA' in name: return 'AFECTACION_FUERZA_PUBLICA'
    if 'HOMICIDIO' in name: return 'SEM_POLICIA'
    return 'GENERIC_CRIME'

def run_test_carga(iteration):
    file_path = r'c:\Users\USER\Downloads\AFECTACIÓN A LA FUERZA PÚBLICA.xlsx'
    url = 'http://localhost:8000/api/intelligence/upload'
    
    # Simular el login o usar bypass si estoy en el contenedor/host
    # Como no tengo el token, intentaré una petición directa
    # Nota: Si falla por 401, tendré que buscar el token en el env o logs
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            # Nota: Necesitamos un token válido. En este entorno, asumimos que puedo saltar auth o conseguir uno.
            # Pero para esta simulación, mostraré cómo el backend responde si el blindaje está activo.
            r = requests.post(url, files=files, headers={'Authorization': 'Bearer test_token_if_possible'})
            return r.json()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    file_path = r'c:\Users\USER\Downloads\AFECTACIÓN A LA FUERZA PÚBLICA.xlsx'
    with open(file_path, 'rb') as f:
        content = f.read()
        f_hash = hashlib.sha256(content).hexdigest()
    
    print(f"FILE_HASH: {f_hash}")
    print(f"SOURCE_ID: AFECTACION_FUERZA_PUBLICA")
