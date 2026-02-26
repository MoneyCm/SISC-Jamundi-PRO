import sys
import os
sys.path.append(os.getcwd())

from db.models import SessionLocal
from services.report_automation_service import ReportAutomationService
from services.rnmc_service import RNMCService
import json

def verify_rnmc_pdf():
    db = SessionLocal()
    print("Iniciando validación de PDF RNMC...")
    
    # 1. Forzar generación de reporte SEMANAL para la última semana disponible
    # Si no hay datos, fallará, pero en nuestro ambiente de prueba debería haber.
    report = ReportAutomationService.run_rnmc_report(db, "SEMANAL", forces=True)
    
    if not report:
        print("Error: No se pudo generar el reporte (posible falta de datos).")
        return

    print(f"Reporte generado con ID: {report.id}")
    print(f"Periodo: {report.period_key}")
    print(f"PDF Path: {report.pdf_path}")
    
    # 2. Verificar contenido del JSON (KPIs y Alertas)
    data = report.output_json
    actual = data["actual"]
    
    print("\n--- Verificación de KPIs ---")
    print(f"Total Medidas: {actual['total_registros']}")
    print(f"Recaudo: {actual['recaudo_total']}")
    print(f"Efectividad: {actual.get('porcentaje_pagado', 0)}%")
    
    print("\n--- Verificación de Alertas ---")
    alertas = actual.get("alertas", {})
    print(f"Rezagos en Proceso (>30d): {len(alertas.get('rezago_proceso', []))}")
    print(f"Impagos Ratificados: {len(alertas.get('impagos_ratificados', []))}")
    
    if report.pdf_path and os.path.exists(report.pdf_path):
        print(f"\n✅ EXITO: El archivo PDF existe en {report.pdf_path}")
        print(f"Hash Integridad: {report.pdf_sha256}")
    else:
        print(f"\n❌ ERROR: El archivo PDF no fue encontrado.")

    db.close()

if __name__ == "__main__":
    verify_rnmc_pdf()
