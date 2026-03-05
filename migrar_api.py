import requests, psycopg2
RENDER_API = "https://sisc-backend.onrender.com/api/analitica/incidencias"
NEON_URL = "postgresql://neondb_owner:npg_5NY7BeOiHqoX@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
def migrar():
    print("Conectando a Render...")
    try:
        r = requests.get(RENDER_API, timeout=60)
        if r.status_code != 200:
            print("Error Render")
            return
        datos = r.json()
        print(f"Datos: {len(datos)}")
        conn = psycopg2.connect(NEON_URL)
        cur = conn.cursor()
        for i in datos:
            try:
                cur.execute("INSERT INTO incidentes (id_externo, tipo, barrio, fecha, hora, estado, latitud, longitud, descripcion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (str(i.get('id_externo', i.get('id'))), i.get('tipo'), i.get('barrio'), i.get('fecha'), i.get('hora'), i.get('estado'), i.get('latitud'), i.get('longitud'), i.get('descripcion')))
            except: pass
        conn.commit()
        cur.close(); conn.close()
        print("MIGRACION OK")
    except Exception as e: print(f"Error: {e}")
if __name__ == "__main__": migrar()
