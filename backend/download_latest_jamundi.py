import requests
import sys

def download_jamundi_latest(dataset_id, name):
    # Orden descendente para asegurar 2024-2026
    url = "https://www.datos.gov.co/resource/" + dataset_id + ".csv?municipio=JAMUNDI&$order=fecha_hecho DESC&$limit=2000"
    
    print("Descargando " + name + " (RECIENTES) de JAMUNDI...")
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            lines = r.text.strip().split("\n")
            if len(lines) > 1:
                filename = "backend/JAMUNDI_LATEST_" + name + ".csv"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(r.text)
                print("Guardado: " + filename + " (" + str(len(lines)-1) + " registros)")
                return True
            else:
                print("No se encontraron registros")
                return False
        else:
            print("Error HTTP " + str(r.status_code))
            return False
    except Exception as e:
        print("Error: " + str(e))
        return False

if __name__ == "__main__":
    targets = [
        ("m8fd-ahd9", "HOMICIDIO"),
        ("4rxi-8m8d", "HURTO_PERSONAS"),
        ("7i2x-h5vp", "HURTO_COMERCIO"),
        ("7mn7-vzqp", "HURTO_RESIDENCIAS")
    ]
    for rid, name in targets:
        download_jamundi_latest(rid, name)
