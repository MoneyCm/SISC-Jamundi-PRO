from sqlalchemy.orm import Session
from db.models import SessionLocal
from db.models_dq import DqReport, DqIssue
import json

def debug_last_dq():
    db = SessionLocal()
    try:
        last_report = db.query(DqReport).order_by(DqReport.created_at.desc()).first()
        if not last_report:
            print("No se encontraron reportes de calidad (DQ) en la base de datos.")
            return
            
        print(f"--- ÚLTIMO REPORTE DE CALIDAD ---")
        print(f"ID: {last_report.id}")
        print(f"Archivo: {last_report.filename}")
        print(f"Fuente: {last_report.source_name}")
        print(f"Semáforo: {last_report.semaforo}")
        print(f"Score: {last_report.score_overall}")
        print(f"Filas Totales: {last_report.rows_total}")
        
        if last_report.missing_cols:
            print(f"Columnas Faltantes: {last_report.missing_cols}")
            
        print("\n--- HALLAZGOS (ISSUES) ---")
        issues = db.query(DqIssue).filter(DqIssue.report_id == last_report.id).all()
        for issue in issues:
            print(f"[{issue.severity}] Campo: {issue.field} | Regla: {issue.rule} | Conteo: {issue.count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    debug_last_dq()
