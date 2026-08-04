from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("--- INVESTIGACION HOMICIDIOS POLICIA_SEMANAL ---")
    
    # 1. Ver qué conductas originales se están mapeando a Homicidio
    print("\nCategorías mapeadas como HOMICIDIO:")
    res = conn.execute(text("""
        SELECT conducta_original, conducta_estandar, count(*) 
        FROM hechos_seguridad 
        WHERE fuente_codigo = 'POLICIA_SEMANAL' 
        AND conducta_estandar = 'Homicidio'
        GROUP BY conducta_original, conducta_estandar
    """)).fetchall()
    for row in res:
        print(f"Original: {row[0]} -> Estándar: {row[1]} | Cantidad: {row[2]}")

    # 2. Ver conductas que NO se mapearon a Homicidio pero podrían serlo
    print("\nConductas NO mapeadas que contienen 'MUERTE' o 'HOMICIDIO':")
    res = conn.execute(text("""
        SELECT conducta_original, conducta_estandar, count(*) 
        FROM hechos_seguridad 
        WHERE fuente_codigo = 'POLICIA_SEMANAL' 
        AND conducta_estandar != 'Homicidio'
        AND (conducta_original ILIKE '%HOMICIDIO%' OR conducta_original ILIKE '%MUERTE%')
        GROUP BY conducta_original, conducta_estandar
    """)).fetchall()
    for row in res:
        print(f"Original: {row[0]} -> Estándar: {row[1]} | Cantidad: {row[2]}")

    # 3. Ver registros RECHAZADOS o DUPLICADOS en el último Run
    print("\nResumen del último Run de Ingesta:")
    run = conn.execute(text("SELECT id, filename, aprobadas, rechazadas, duplicadas, fuera_territorio FROM ingestion_runs WHERE fuente_codigo = 'POLICIA_SEMANAL' ORDER BY fecha_inicio DESC LIMIT 1")).fetchone()
    if run:
        print(f"File: {run.filename} | Aprobadas: {run.aprobadas} | Rechazadas: {run.rechazadas} | Duplicadas: {run.duplicadas} | Fuera Jamundí: {run.fuera_territorio}")
        
        if run.rechazadas > 0 or run.duplicadas > 0:
            print("\nDetalle de problemas (Issues) en el último Run:")
            issues = conn.execute(text("SELECT regla, descripcion, count(*) FROM ingestion_issues WHERE ingestion_id = :id GROUP BY regla, descripcion"), {"id": run.id}).fetchall()
            for issue in issues:
                print(f"[{issue.regla}] {issue.descripcion} | Total: {issue.count}")
