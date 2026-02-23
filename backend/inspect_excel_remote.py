import requests
import pandas as pd
import io
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def inspect_mindefensa():
    url = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTEBDF030F568F49A4A73563ADB8DBA8AB/native/HURTO%20PERSONAS.xlsx"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    }
    cookies = {"siteId": "Sitio-Web-Ministerio-Defensa"}
    
    print(f"Descargando {url}...")
    resp = requests.get(url, headers=headers, cookies=cookies, verify=False, timeout=30)
    if resp.status_code != 200:
        print(f"Error: status {resp.status_code}")
        return

    print("Archivo descargado. Analizando...")
    df_raw = pd.read_excel(io.BytesIO(resp.content), header=None, nrows=20)
    
    header_idx = -1
    for idx, row in df_raw.head(20).iterrows():
        row_str = [str(x).upper().strip() for x in row.values if pd.notna(x)]
        if any("MUNICIPIO" in v for v in row_str):
            header_idx = idx
            print(f"Header encontrado en fila: {header_idx}")
            print(f"Contenido de la fila: {row_str}")
            break
    
    if header_idx != -1:
        df = pd.read_excel(io.BytesIO(resp.content), header=header_idx)
        print(f"Columnas detectadas (normalizadas por pandas):")
        print(df.columns.tolist())
    else:
        print("No se encontró el header MUNICIPIO.")

if __name__ == "__main__":
    inspect_mindefensa()
