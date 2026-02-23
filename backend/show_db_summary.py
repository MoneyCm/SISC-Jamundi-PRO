from db.models import engine
from db.models_intelligence import NationalCrimeStats
from sqlalchemy.orm import Session
from sqlalchemy import func

with Session(engine) as db:
    recs = db.query(
        NationalCrimeStats.anio,
        NationalCrimeStats.tipo_delito,
        NationalCrimeStats.fuente_archivo,
        func.sum(NationalCrimeStats.cantidad).label('total_casos')
    ).group_by(
        NationalCrimeStats.anio,
        NationalCrimeStats.tipo_delito,
        NationalCrimeStats.fuente_archivo
    ).order_by(NationalCrimeStats.tipo_delito).all()
    
    print("| Año | Tipo de Delito | Fuente Original (Excel) | Casos Totales |")
    print("| :--- | :--- | :--- | :--- |")
    for r in recs:
        print(f"| {r.anio} | {r.tipo_delito} | {r.fuente_archivo} | {int(r.total_casos)} |")
