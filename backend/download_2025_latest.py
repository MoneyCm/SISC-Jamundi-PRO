import requests
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_latest_2025():
    # Esta es la URL del archivo consolidado de 2025 que detecté en la página
    asset_id = "CONT70A072EBE9BE4F6FBB568889CC7B9BE9"
    filename = "INDICADORES%20DE%20SEGUR%20Y%20RESULT%20OPER%20ENERO-DICIEMBRE%202025.xlsx"
    url = f"https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/{asset_id}/native/{filename}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica",
        "Accept": "*/*"
    }
    
    cookies = {
        "siteId": "Sitio-Web-Ministerio-Defensa"
    }

    print(f"📥 Intentando descargar el archivo más reciente de 2025...")
    try:
        response = requests.get(url, headers=headers, cookies=cookies, verify=False, timeout=60)
        
        if response.status_code == 200:
            target_path = "backend/INDICADORES_SISC_2025_LATEST.xlsx"
            with open(target_path, "wb") as f:
                f.write(response.content)
            print(f"✅ ¡Éxito! Archivo guardado en: {target_path}")
            print(f"📏 Tamaño: {len(response.content) / 1024 / 1024:.2f} MB")
            return True
        else:
            print(f"❌ Fallo en la descarga. Código HTTP: {response.status_code}")
            # Si falla el XLSX, intentamos el PDF que también vi en la web
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    download_latest_2025()
