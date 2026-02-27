import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SessionLocal
from db.models_intelligence import NationalCrimeStats
from sqlalchemy import func

def diag():
    db = SessionLocal()
    try:
        # 1. Ver municipios
        muni = db.query(NationalCrimeStats.municipio_normalizado).distinct().all()
        print("Municipios en DB:", muni)
        
        # 2. Ver delitos para Jamundi
        delitos = db.query(NationalCrimeStats.tipo_delito).filter(
            NationalCrimeStats.municipio_normalizado.ilike('%JAMUNDI%')
        ).distinct().all()
        print("Delitos para Jamundi:", delitos)
        
        # 3. Ver años para Jamundi
        anos = db.query(NationalCrimeStats.anio).filter(
            NationalCrimeStats.municipio_normalizado.ilike('%JAMUNDI%')
        ).distinct().all()
        print("Años para Jamundi:", anos)
        
    finally:
        db.close()

if __name__ == "__main__":
    diag()
