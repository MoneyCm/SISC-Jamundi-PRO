import pandas as pd
import requests
import json

# Configuración
csv_path = r'C:\Users\USER\Downloads\SISC_Reporte_2026-02-05.csv'
api_url = 'https://sisc-backend.onrender.com/ingesta/bulk' # Usamos el endpoint de ingesta masiva

try:
    df = pd.read_csv(csv_path)
    data = []
    
    for _, row in df.iterrows():
        # Coordenadas por defecto para Jamundí si no tiene
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
            "descripcion": f"Incidente de {row['Tipo']} en {row['Barrio']} sincronizado desde local."
        }
        data.append(item)

    print(f"Sincronizando {len(data)} registros con la producción...")
    response = requests.post(api_url, json=data)
    
    if response.status_code == 200:
        print("✅ Sincronización exitosa.")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Error en la sincronización: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error leyendo el archivo o conectando: {e}")
