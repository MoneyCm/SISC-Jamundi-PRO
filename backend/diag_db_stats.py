import sqlite3
import os

db_path = 'C:/Proyectos/SISC-Jamundi-PRO/backend/dian_sim.db'

if not os.path.exists(db_path):
    print(f"ERROR: No se encuentra la base de datos en {db_path}")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- DIAGNÓSTICO DE BASE DE DATOS (NationalCrimeStats) ---")

try:
    # 1. Conteo total por año para Jamundí en homicidios
    query = """
    SELECT anio, SUM(cantidad) as total, COUNT(*) as registros
    FROM national_crime_stats
    WHERE municipio_normalizado = 'JAMUNDI' AND tipo_delito LIKE '%HOMICIDIO%'
    GROUP BY anio
    ORDER BY anio DESC
    """
    cursor.execute(query)
    results = cursor.fetchall()
    
    if not results:
        print("❌ No se encontraron datos de HOMICIDIO para JAMUNDI en la tabla NationalCrimeStats.")
    else:
        print("📊 Homicidios por año en Jamundí:")
        for anio, total, registros in results:
            print(f"   Año {anio}: {total} homicidios ({registros} registros)")

    # 2. Verificar nombres de delitos disponibles
    print("\n📝 Tipos de delitos registrados en la tabla:")
    cursor.execute("SELECT DISTINCT tipo_delito FROM national_crime_stats LIMIT 10")
    delitos = cursor.fetchall()
    for (d,) in delitos:
        print(f"   - {d}")

except Exception as e:
    print(f"❌ Error consultando la base de datos: {e}")

conn.close()
