import sqlalchemy
from db.models import engine
from db.models_intelligence import NationalCrimeStats
from sqlalchemy.orm import Session

with Session(engine) as db:
    recs = db.query(NationalCrimeStats.fecha_hecho, NationalCrimeStats.fuente_archivo, NationalCrimeStats.municipio_normalizado).limit(20).all()
    print("Registros de fechas en DB:")
    for r in recs:
        print(r)
