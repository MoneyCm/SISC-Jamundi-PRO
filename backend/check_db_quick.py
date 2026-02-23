import os
import sys
from sqlalchemy import create_engine, text

# Forzar encoding UTF-8 para evitar errores en Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

# Usar el string de conexión de .env directamente
DATABASE_URL = "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi"

try:
    # Añadimos connect_args para evitar el UnicodeDecodeError que vimos antes
    engine = create_engine(DATABASE_URL, connect_args={"client_encoding": "utf8"})
    with engine.connect() as conn:
        res = conn.execute(text("""
            SELECT anio, tipo_delito, municipio_normalizado, sum(cantidad) as total 
            FROM national_crime_stats 
            GROUP BY anio, tipo_delito, municipio_normalizado 
            ORDER BY anio DESC, tipo_delito, municipio_normalizado
        """))
        rows = res.fetchall()
        print(f"{'Año':<6} | {'Delito':<25} | {'Municipio':<15} | {'Total':<10}")
        print("-" * 65)
        for r in rows:
            print(f"{r[0]:<6} | {r[1]:<25} | {r[2]:<15} | {int(r[3]):<10}")

except Exception as e:
    print(f"ERROR: {e}")
