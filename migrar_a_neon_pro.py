import psycopg2
from psycopg2 import extras

RENDER_URL = "postgresql://sisc_db_user:JdeJQpA5E14WHsxKxmdlVFYYsadkyBF7@dpg-d60k5hnpm1nc73cu20qg-a.oregon-postgres.render.com/sisc_db"
NEON_URL = "postgresql://neondb_owner:npg_5NY7BeOiHqoX@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
TABLAS = ["roles", "users", "incidentes", "reports", "intelligence_items", "participation_items"]

def migrar():
    print("MIGRACION DE DATOS: RENDER -> NEON")
    try:
        conn_render = psycopg2.connect(RENDER_URL)
        conn_neon = psycopg2.connect(NEON_URL)
        cur_render = conn_render.cursor(cursor_factory=extras.RealDictCursor)
        cur_neon = conn_neon.cursor()

        for tabla in TABLAS:
            print(f"📦 Procesando tabla: {tabla}...", end="", flush=True)
            try:
                cur_render.execute(f"SELECT * FROM {tabla}")
                rows = cur_render.fetchall()
                if not rows:
                    print(" (Vacía, omitiendo)")
                    continue
                columns = rows[0].keys()
                query = f"INSERT INTO {tabla} ({', '.join(columns)}) VALUES ({', '.join(['%s']*len(columns))}) ON CONFLICT DO NOTHING"
                values = [tuple(row.values()) for row in rows]
                extras.execute_batch(cur_neon, query, values)
                conn_neon.commit()
                print(f" ✅ OK ({len(rows)} registros)")
            except Exception as e:
                print(f" ❌ ERROR en tabla {tabla}: {e}")
                conn_neon.rollback()

        cur_render.close(); cur_neon.close()
        conn_render.close(); conn_neon.close()
        print("\n✅ MIGRACIÓN COMPLETADA CON ÉXITO")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")

if __name__ == "__main__":
    migrar()
