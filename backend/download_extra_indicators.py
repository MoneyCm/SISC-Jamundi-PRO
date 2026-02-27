import requests
import sys

def download_new_indicators(dataset_id, name):
    url = "https://www.datos.gov.co/resource/" + dataset_id + ".csv?municipio=JAMUNDI&$order=fecha_hecho DESC&$limit=2000"
    print("Descargando " + name + "...")
    try:
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            if len(lines) > 1:
                filename = "backend/JAMUNDI_EXTRA_" + name + ".csv"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(r.text)
                print("OK: " + filename + " (" + str(len(lines)-1) + " registros)")
                return True
            else:
                print("Sin datos")
        else:
            print("Error " + str(r.status_code))
    except Exception as e:
        print("Error: " + str(e))
    return False

if __name__ == "__main__":
    targets = [
        ("q2ib-t9am", "EXTORSION"),
        ("csb4-y6v2", "HURTO_VEHICULOS"),
        ("jr6v-i33g", "LESIONES_PERSONALES"),
        ("ct3k-bssu", "AMENAZAS")
    ]
    for rid, name in targets:
        download_new_indicators(rid, name)
