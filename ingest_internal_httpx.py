import pandas as pd
import httpx
import json
import os
import asyncio

async def main():
    csv_path = 'report_temp.csv'
    api_url = 'http://localhost:8000/ingesta/bulk'

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        return

    df = pd.read_csv(csv_path)

    data = []
    for _, row in df.iterrows():
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
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(api_url, json=data)
            print(f"Respuesta del servidor: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error llamando al API: {e}")

if __name__ == "__main__":
    asyncio.run(main())
