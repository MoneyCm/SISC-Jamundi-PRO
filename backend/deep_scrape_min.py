import requests
import urllib3
import re
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def deep_scrape_mindefensa():
    url = "https://www.mindefensa.gov.co/defensa-y-seguridad/datos-y-cifras/informacion-estadistica"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    
    print(f"🕵️ Escaneando profundamente {url}...")
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=30)
        if r.status_code != 200:
            print(f"❌ Error HTTP {r.status_code}")
            return
            
        html = r.text
        # Buscar IDs de activos digitales de Oracle (CONT...)
        cont_ids = re.findall(r'CONT[A-Z0-9]{32}', html)
        print(f"📦 IDs de activos encontrados: {len(cont_ids)}")
        
        # Buscar nombres de archivos .xlsx
        xlsx_files = re.findall(r'"([^"]*?\.xlsx)"', html, re.I)
        print(f"📊 Archivos Excel mencionados: {len(xlsx_files)}")
        
        # Intentar relacionar IDs con nombres
        # El CMS suele ponerlos cerca en estructuras JSON
        found_links = []
        for asset_id in set(cont_ids):
            # Buscar el nombre del archivo cerca del ID en el HTML
            pos = html.find(asset_id)
            snippet = html[pos:pos+500]
            name_match = re.search(r'"([^"]*?\.xlsx)"', snippet, re.I)
            if name_match:
                found_links.append((asset_id, name_match.group(1)))

        for aid, name in found_links:
            print(f"🔗 Posible link: {name} (ID: {aid})")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    deep_scrape_mindefensa()
