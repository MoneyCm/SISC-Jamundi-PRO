import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def find_2024_links():
    # El Ministerio suele tener una URL para históricos o cambia los IDs
    # Voy a probar con patrones comunes de IDs que vi en el scraper antiguo
    base_api = "https://www.mindefensa.gov.co/sites/web/content/management/api/v1.1/assets/{id}/native/{name}"
    
    # IDs conocidos del scraper antiguo (que podrían seguir vivos si no los borraron)
    potential_ids = [
        "CONTD2155DC1726D4A21B0B8267F91325AB5", # Homicidio
        "CONTEBDF030F568F49A4A73563ADB8DBA8AB", # Hurto Personas
        "CONT1F6023E051B746DAA1F3E4075209A882", # Hurto Comercio
        "CONT278B01DD860B435DB5ECC2AB6ABC3EDB", # Hurto Residencias
        "CONT7154F2FB1B264CDCAD9A48A3BEE58A77", # Extorsión
        "CONT2BF65517CF044CC19DD6CB5BB4A7B411", # Hurto Vehículos
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for aid in potential_ids:
        # Probar con nombres de archivo de 2024
        # El Ministerio a veces cambia el nombre pero el ID se mantiene un tiempo
        url = base_api.format(id=aid, name="HOMICIDIO%20INTENCIONAL.xlsx") # Ejemplo
        try:
            r = requests.head(url, headers=headers, verify=False, timeout=10)
            if r.status_code == 200:
                print(f"✅ VIVO: {aid} (Size: {r.headers.get('Content-Length')})")
            else:
                print(f"❌ MUERTO: {aid} (Status: {r.status_code})")
        except:
            pass

if __name__ == "__main__":
    find_2024_links()
