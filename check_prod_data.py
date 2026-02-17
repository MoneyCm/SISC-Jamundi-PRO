import urllib.request
import json
import ssl

def check_prod():
    # Desactivar verificación SSL si es necesario (para entornos corporativos), 
    # aunque lo ideal es que onrender.com tenga certificados válidos.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    base_url = "https://sisc-backend.onrender.com"
    endpoints = [
        "/analitica/estadisticas/kpis",
        "/analitica/estadisticas/tendencia",
        "/analitica/estadisticas/distribucion",
        "/analitica/eventos/geojson"
    ]

    print(f"--- VERIFICANDO PRODUCCIÓN: {base_url} ---")
    
    for ep in endpoints:
        url = base_url + ep
        print(f"Probando {url}...", end=" ")
        try:
            with urllib.request.urlopen(url, context=ctx, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if ep == "/analitica/eventos/geojson":
                        count = len(data.get('features', []))
                    elif isinstance(data, list):
                        count = len(data)
                    elif isinstance(data, dict):
                        count = data.get('total_incidentes', 0)
                    else:
                        count = "Desconocido"
                    print(f"✅ OK. Registros: {count}")
                else:
                    print(f"❌ ERROR. Status: {response.status}")
        except Exception as e:
            print(f"❌ FALLO: {e}")

if __name__ == "__main__":
    check_prod()
