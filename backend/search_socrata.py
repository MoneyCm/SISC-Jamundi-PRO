import requests
import json

def search_datos_gov():
    # API de búsqueda de Socrata (datos.gov.co)
    search_url = "https://api.us.socrata.com/api/catalog/v1?q=Ministerio%20de%20Defensa%20Homicidio&domains=www.datos.gov.co"
    
    print("🔍 Buscando datasets de Homicidio en Datos Abiertos...")
    try:
        r = requests.get(search_url, timeout=20)
        data = r.json()
        
        results = data.get('results', [])
        print(f"📦 Encontrados {len(results)} resultados.")
        
        for res in results:
            resource = res.get('resource', {})
            name = resource.get('name')
            rid = resource.get('id')
            updated = resource.get('updatedAt')
            print(f"✅ {name} (ID: {rid}) - Actualizado: {updated}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    search_datos_gov()
