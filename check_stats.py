import sys
import os

# Añadir el path del backend para importar modelos
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.models import SessionLocal
from db.models_intelligence import NationalCrimeStats
from sqlalchemy import func

def check_stats():
    db = SessionLocal()
    anio = 2025
    tipo_delito = "Homicidio Intencional"
    
    # 1. Datos de Jamundí
    jamundi = db.query(
        func.sum(NationalCrimeStats.cantidad)
    ).filter(
        NationalCrimeStats.municipio_normalizado == "JAMUNDI",
        NationalCrimeStats.anio == anio,
        NationalCrimeStats.tipo_delito == tipo_delito
    ).scalar() or 0
    
    # 2. Promedio nacional (mi nueva lógica)
    subquery = db.query(
        NationalCrimeStats.municipio_normalizado,
        func.sum(NationalCrimeStats.cantidad).label("total_municipio")
    ).filter(
        NationalCrimeStats.anio == anio,
        NationalCrimeStats.tipo_delito == tipo_delito
    ).group_by(
        NationalCrimeStats.municipio_normalizado
    ).subquery()

    avg_nacional = db.query(
        func.avg(subquery.c.total_municipio)
    ).scalar() or 0
    
    # 3. Conteo de municipios reportando
    count_municipios = db.query(
        func.count(func.distinct(NationalCrimeStats.municipio_normalizado))
    ).filter(
        NationalCrimeStats.anio == anio,
        NationalCrimeStats.tipo_delito == tipo_delito
    ).scalar() or 0

    print(f"ANIO: {anio}")
    print(f"DELITO: {tipo_delito}")
    print(f"JAMUNDI TOTAL: {jamundi}")
    print(f"PROMEDIO NACIONAL (de {count_municipios} municipios): {avg_nacional}")
    if avg_nacional > 0:
        diff = (jamundi - avg_nacional) / avg_nacional * 100
        print(f"DIFERENCIA: {diff:.2f}%")
    
    db.close()

if __name__ == "__main__":
    check_stats()
