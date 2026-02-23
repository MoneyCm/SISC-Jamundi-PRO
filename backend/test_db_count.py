from db.models import SessionLocal
from db.models_intelligence import NationalCrimeStats
from sqlalchemy import select, func

db = SessionLocal()
count = db.execute(select(func.count(NationalCrimeStats.id)).where(NationalCrimeStats.anio == 2025)).scalar_one()
print(f"Total registros 2025 en DB: {count}")

latest_records = db.execute(select(NationalCrimeStats).where(NationalCrimeStats.anio == 2025).order_by(NationalCrimeStats.id.desc()).limit(15)).scalars().all()
print("Últimos registros 2025 insertados:")
for r in latest_records:
    print(f"- {r.municipio} / {r.mes} ({r.fecha_hecho}): {r.tipo_delito}")
