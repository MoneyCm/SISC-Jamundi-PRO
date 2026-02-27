import pandas as pd
import sys
import os
from sqlalchemy import create_engine, text

# Ajustar path para importar desde backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from db.session import SQLALCHEMY_DATABASE_URL

def generate_yoy_report():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    query = """
    SELECT 
        tipo_delito,
        anio,
        SUM(cantidad) as total
    FROM national_crime_stats
    WHERE municipio_normalizado = 'JAMUNDI'
      AND anio IN (2024, 2025)
      AND tipo_delito IN ('HOMICIDIO', 'HURTO_PERSONAS', 'HURTO_COMERCIO', 'HURTO_RESIDENCIAS')
    GROUP BY tipo_delito, anio
    ORDER BY tipo_delito, anio
    """
    
    print("REPORTE COMPARATIVO YoY (2024 vs 2025) - JAMUNDI")
    
    try:
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("No se encontraron datos.")
            return

        report = df.pivot(index='tipo_delito', columns='anio', values='total').fillna(0)
        
        # Variación
        report['Absoluta'] = report[2025] - report[2024]
        report['% Cambio'] = report.apply(
            lambda x: str(round(((x[2025] - x[2024]) / x[2024] * 100), 1)) + "%" if x[2024] > 0 else "N/A", 
            axis=1
        )
        
        print("\nResultados:")
        print(report.to_string())
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    generate_yoy_report()
