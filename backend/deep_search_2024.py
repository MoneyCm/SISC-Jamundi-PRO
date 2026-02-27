import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def deep_search_2024():
    url = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com/"
    }
    
    print(f"🔎 Buscando datasets de 2024 en {url}...")
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=30)
        html = r.text
        
        # Buscar menciones a 2024 cerca de archivos .xlsx
        # Oracle CMS pone los links así: "imageHrefName":"HOMICIDIO 2024.xlsx", "contentId":"CONT..."
        matches = re.findall(r'"contentId":"(CONT.*?)".*?"imageHrefName":"(.*?2024.*?\.xlsx)"', html, re.I)
        
        if not matches:
            # Probar sin el año en el nombre pero que contenga 2024 en el contexto
            matches = re.findall(r'"contentId":"(CONT.*?)".*?"imageHrefName":"(.*?\.xlsx)"', html, re.I)
            
        print(f"📊 Encontrados {len(matches)} archivos Excel potenciales.")
        
        for asset_id, filename in matches:
            # Probar si el archivo es reciente (2024 o 2025)
            # El Ministerio usa nombres como "HOMICIDIO INTENCIONAL.xlsx" para el consolidado actual
            print(f"🔗 Encontrado: {filename} (ID: {asset_id})")
            
            # Probar URL
            test_url = f"https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/{asset_id}/native/{filename.replace(' ', '%20')}"
            try:
                resp = requests.head(test_url, headers=headers, verify=False, timeout=10)
                if resp.status_code == 200:
                    print(f"   ✅ VIVO: {test_url} (Size: {resp.headers.get('Content-Length')})")
                else:
                    print(f"   ❌ MUERTO: {resp.status_code}")
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    deep_search_2024()
