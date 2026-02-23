import sqlalchemy
from db.models import engine
from db.models_intelligence import NationalCrimeStats
from sqlalchemy.orm import Session
from sqlalchemy import func

with Session(engine) as db:
    anios = db.query(NationalCrimeStats.anio, func.count(NationalCrimeStats.id)).group_by(NationalCrimeStats.anio).order_by(NationalCrimeStats.anio).all()
    print("Registros por año:")
    for a, c in anios:
        print(f"Año {a}: {c} registros")
