import pandas as pd
import requests
import json

csv_path = r'C:\Users\USER\Downloads\SISC_Reporte_2026-02-05.csv'
api_url = 'http://localhost:8000/ingesta/bulk'

df = pd.read_csv(csv_path)

data = []
for _, row in df.iterrows():
    # Jamundí reference coordinates
    lat, lng = 3.26, -76.53
    
    item = {
        "id_externo": str(row['ID']),
        "tipo": str(row['Tipo']),
        "barrio": str(row['Barrio']),
        "fecha": str(row['Fecha']),
        "hora": "00:00",
        "estado": str(row['Estado']),
        "latitud": lat,
        "longitud": lng,
        "descripcion": f"Incidente de {row['Tipo']} en {row['Barrio']} extraído de reporte SISC."
    }
    data.append(item)

print(f"Enviando {len(data)} registros al API...")
response = requests.post(api_url, json=data)
print(f"Respuesta del servidor: {response.status_code}")
print(json.dumps(response.json(), indent=2))
