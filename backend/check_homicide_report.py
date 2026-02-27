from db.session import SessionLocal
from db.models_dq import DqReport
import json

def get_last_homicide_report():
    db = SessionLocal()
    try:
        # Buscar el último reporte que mencione HOMICIDIO en su nombre de fuente o archivo
        report = db.query(DqReport).filter(
            (DqReport.source_name.ilike('%HOMICIDIO%')) | 
            (DqReport.filename.ilike('%HOMICIDIO%'))
        ).order_by(DqReport.created_at.desc()).first()
        
        if not report:
            print("No se encontraron reportes de calidad para HOMICIDIOS.")
            return

        print(f"--- REPORTE DE CALIDAD: HOMICIDIOS ---")
        print(f"ID: {report.id}")
        print(f"Archivo: {report.filename}")
        print(f"Fuente: {report.source_name}")
        print(f"Fecha Ingesta: {report.created_at}")
        print(f"Total Filas: {report.rows_total}")
        print(f"Puntaje General: {report.score_overall}/100")
        print(f"Cantidad de Hallazgos: {len(report.issues)}")
        
        if report.report_json and "summary" in report.report_json:
            print("\nResumen Detallado:")
            print(json.dumps(report.report_json["summary"], indent=4))
            
    finally:
        db.close()

if __name__ == "__main__":
    get_last_homicide_report()
