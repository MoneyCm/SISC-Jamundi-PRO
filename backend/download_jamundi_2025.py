import requests
import sys

def download_jamundi_data(dataset_id, name):
    # Socrata Query: ?municipio=JAMUNDÍ (standard name)
    # The API is case-sensitive for values but usually MinDefensa uses uppercase
    url = f"https://www.datos.gov.co/resource/{dataset_id}.csv?municipio=JAMUNDÍ"
    
    print(f"📥 Descargando {name} de JAMUNDÍ...")
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            if len(lines) > 1:
                filename = f"backend/JAMUNDI_2025_{name}.csv"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(r.text)
                print(f"✅ Guardado: {filename} ({len(lines)-1} registros)")
                return True
            else:
                # Try lowercase/uppercase variants if no result
                print(f"⚠️ Sin resultados para JAMUNDÍ. Probando JAMUNDI (sin tilde)...")
                url_alt = f"https://www.datos.gov.co/resource/{dataset_id}.csv?municipio=JAMUNDI"
                r = requests.get(url_alt, timeout=60)
                lines = r.text.strip().split('\n')
                if len(lines) > 1:
                    filename = f"backend/JAMUNDI_2025_{name}.csv"
                    with open(filename, "w", encoding='utf-8') as f:
                        f.write(r.text)
                    print(f"✅ Guardado (sin tilde): {filename} ({len(lines)-1} registros)")
                    return True
                else:
                    print(f"❌ No se encontró data de Jamundí en {name}")
                    return False
        else:
            print(f"❌ Error HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    targets = [
        ("m8fd-ahd9", "HOMICIDIO"),
        ("4rxi-8m8d", "HURTO_PERSONAS"),
        ("gepp-dxcs", "VIOLENCIA_INTRAFAMILIAR"),
        ("bz43-8ahq", "DELITOS_SEXUALES"),
        ("8rpn-wpty", "FUERZA_PUBLICA")
    ]
    for rid, name in targets:
        download_jamundi_data(rid, name)
