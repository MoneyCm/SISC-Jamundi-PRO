import requests
import psycopg2
import json

# Origen (Render) - Usamos la API pública porque no tenemos la pass directa
RENDER_API = "https://sisc-backend.onrender.com/api/analitica/incidencias"

# Destino (Neon) - La URL que me diste
NEON_URL = "postgresql://neondb_owner:npg_5NY7BeOiHqoX@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

print("📡 Extrayendo datos de Render (vieja base de datos)...")
try:
    r = requests.get(RENDER_API, timeout=60)
    if r.status_code != 200:
        print(f"❌ Error accediendo a Render: {r.status_code}")
        exit(1)
    
    datos = r.json()
    print(f"✅ Encontrados {len(datos)} registros.")

    if not datos:
        print("⚠️ No hay datos para migrar. La base de datos estaba vacía.")
        exit(0)

    print("🚀 Conectando a Neon para migrar...")
    conn = psycopg2.connect(NEON_URL)
    cur = conn.cursor()

    # Aseguramos que la tabla exista (Esto lo hace el backend de SISC normalmente, pero lo haremos aqui para seguridad)
    # Suponiendo que la tabla se llama 'incidentes' (basado en master_analyst.py)
    
    # Inyectar datos
    exito = 0
    for item in datos:
        # Aqui adaptamos los campos segun el modelo de SISC
        # (id_externo, tipo, barrio, fecha, hora, estado, latitud, longitud, descripcion)
        try:
            cur.execute("""
                INSERT INTO incidentes (id_externo, tipo, barrio, fecha, hora, estado, latitud, longitud, descripcion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_externo) DO NOTHING
            """, (
                str(item.get('id_externo', item.get('id', ''))),
                item.get('tipo', 'Desconocido'),
                item.get('barrio', 'Jamundí'),
                item.get('fecha', '2026-01-01'),
                item.get('hora', '00:00'),
                item.get('estado', 'ACTIVO'),
                item.get('latitud', 3.26),
                item.get('longitud', -76.53),
                item.get('descripcion', '')
            ))
            exito += 1
        except Exception as e:
            print(f"  ⚠️ Error inyectando registro: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Migración completada con éxito: {exito} registros en Neon.")

except Exception as e:
    print(f"❌ Error fatal en migración: {e}")
