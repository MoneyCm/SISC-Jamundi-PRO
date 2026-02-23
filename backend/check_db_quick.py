import os
import sys
from sqlalchemy import create_engine, text

# Forzar encoding UTF-8 para evitar errores en Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

# Usar el string de conexión de .env directamente para evitar problemas de import
DATABASE_URL = "postgresql://sisc_user:sisc_password@localhost:5432/sisc_jamundi"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT anio, count(*) FROM national_crime_stats GROUP BY anio ORDER BY anio"))
        rows = res.fetchall()
        print("RESUMEN DE DATOS EN DATABASE:")
        print("-" * 30)
        if not rows:
            print("LA TABLA ESTA VACIA.")
        for r in rows:
            print(f"Año: {r[0]} | Registros: {r[1]}")
        
        # También chequear municipios únicos para ver si TOTAL NACIONAL está ahí
        res_m = conn.execute(text("SELECT municipio_normalizado, count(*) FROM national_crime_stats WHERE municipio_normalizado = 'TOTAL_NACIONAL' GROUP BY municipio_normalizado"))
        m_rows = res_m.fetchall()
        if m_rows:
            print("-" * 30)
            print(f"Registros de TOTAL_NACIONAL encontrados: {m_rows[0][1]}")
        else:
            print("-" * 30)
            print("NO SE ENCONTRARON REGISTROS DE 'TOTAL_NACIONAL'")

except Exception as e:
    print(f"ERROR: {e}")
