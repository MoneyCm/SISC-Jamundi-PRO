
import sys
import os
from sqlalchemy import text

# Añadir el path al backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.models import SessionLocal
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida
from sqlalchemy import func

def test_stats():
    db = SessionLocal()
    try:
        print("Probando conteo de expedientes...")
        count = db.query(InspeccionExpediente).count()
        print(f"Total expedientes: {count}")
        
        print("Probando stats de estados...")
        estados = db.query(
            InspeccionMedida.estado_actual, 
            func.count(InspeccionMedida.id)
        ).group_by(InspeccionMedida.estado_actual).all()
        print(f"Estados: {estados}")
        
        print("Probando query SQL de expedientes...")
        sql = text("""
            SELECT id, numero_expediente, localidad, 
                   ST_X(geom_punto) as lng, ST_Y(geom_punto) as lat 
            FROM inspeccion_expedientes
            LIMIT 5
        """)
        res = db.execute(sql).fetchall()
        print(f"Resultados SQL: {len(res)} filas")
        for r in res:
            print(f"Exp: {r.numero_expediente}, Lat: {r.lat}")

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_stats()
