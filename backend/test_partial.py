from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import time
import pandas as pd
import io

url = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/CONTD2155DC1726D4A21B0B8267F91325AB5/native/HOMICIDIO%20INTENCIONAL.xlsx"

print("Iniciando test de timeout y parseo parcial...")
scraper = MinDefensaScraper()
processor = NationalStatsProcessor()

content = scraper.download_file(url)
print("Archivo descargado.")

if content:
    df_raw = pd.read_excel(io.BytesIO(content), header=None, nrows=20)
    header_idx = -1
    for idx, row in df_raw.head(20).iterrows():
        row_str = [str(x).upper().strip() for x in row.values if pd.notna(x)]
        if any("MUNICIPIO" in v for v in row_str):
            header_idx = idx
            break
            
    if header_idx != -1:
        print(f"Header en índice {header_idx}")
        # Leer solo 2000 filas para inspeccionar
        df = pd.read_excel(io.BytesIO(content), header=header_idx, nrows=2000)
        df.columns = [str(c).upper().strip().replace(" ", "_") if not pd.isna(c) else "" for c in df.columns]
        
        col_municipio = "MUNICIPIO" if "MUNICIPIO" in df.columns else None
        if col_municipio:
            municipios_unicos = df[col_municipio].dropna().unique()
            print("Muestra de Municipios encontrados en las primeras 2000 filas:")
            print(municipios_unicos[:50])
            
            # Buscar Jamundí
            jamundi_rows = df[df[col_municipio].astype(str).str.contains("JAMUND", na=False, case=False)]
            print(f"Filas que contienen JAMUND: {len(jamundi_rows)}")
        else:
            print(f"No encontró MUNICIPIO. Columnas: {df.columns.tolist()}")
    else:
        print("No encontró header index")
