"""
Script de diagnóstico: muestra los errores DQ del último reporte
de Violencia Intrafamiliar (o cualquier source_name que le indiques).
"""
import sys
import os
import json

# Asegura que el path incluya el backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.session import SessionLocal
from db.models_dq import DqReport, DqIssue
from sqlalchemy import desc

SOURCE_FILTER = "VIOLENCIA_INTRAFAMILIAR"  # Cambia si quieres ver otro dataset

db = SessionLocal()

try:
    # Busca el último reporte que contenga ese source_name (parcial)
    report = (
        db.query(DqReport)
        .filter(DqReport.source_name.ilike(f"%{SOURCE_FILTER}%"))
        .order_by(desc(DqReport.created_at))
        .first()
    )

    if not report:
        print(f"\n[!] No se encontró ningún reporte DQ para '{SOURCE_FILTER}'")
        print("    ¿Ya intentaste cargar el archivo desde la UI?  Si el archivo")
        print("    nunca llegó al gate, no habrá reporte guardado.")
        sys.exit(0)

    print("=" * 70)
    print(f"  REPORTE DQ  —  {report.source_name}")
    print("=" * 70)
    print(f"  ID          : {report.id}")
    print(f"  Archivo     : {report.filename}")
    print(f"  Fecha       : {report.created_at}")
    print(f"  Filas total : {report.rows_total}")
    print(f"  Semáforo    : {report.semaforo}")
    print(f"  Score       : {round((report.score_overall or 0) * 100, 1)}%")
    print(f"  Schema OK   : {report.schema_ok}")
    if report.missing_cols:
        print(f"  Cols faltantes: {report.missing_cols}")
    print()

    # Issues desde la relación (DqIssue table)
    issues = (
        db.query(DqIssue)
        .filter(DqIssue.report_id == report.id)
        .order_by(DqIssue.severity)
        .all()
    )

    # Si no hay en la tabla relacional, intentar desde el JSON guardado
    if not issues and report.report_json and "issues" in report.report_json:
        raw_issues = report.report_json["issues"]
        print(f"  [Hallazgos desde JSON — {len(raw_issues)} issues]\n")
        for i, issue in enumerate(raw_issues, 1):
            sev  = issue.get("severity", "?")
            fld  = issue.get("field", "?")
            rule = issue.get("rule", "?")
            cnt  = issue.get("count", "?")
            mark = "🔴" if sev == "ERROR" else "🟡"
            print(f"  {mark} [{sev}] Campo: {fld}")
            print(f"       Regla : {rule}")
            print(f"       Filas : {cnt}")
            # Mostrar hasta 3 ejemplos
            examples = issue.get("example", [])
            if examples:
                print("       Ej.   :")
                for ex in examples[:3]:
                    print(f"              {json.dumps(ex, ensure_ascii=False, default=str)}")
            print()
    elif issues:
        print(f"  [Hallazgos — {len(issues)} issues]\n")
        for issue in issues:
            mark = "🔴" if issue.severity == "ERROR" else "🟡"
            print(f"  {mark} [{issue.severity}] Campo: {issue.field}")
            print(f"       Regla : {issue.rule}")
            print(f"       Filas : {issue.count}")
            if issue.example:
                examples = issue.example if isinstance(issue.example, list) else [issue.example]
                print("       Ej.   :")
                for ex in examples[:3]:
                    print(f"              {json.dumps(ex, ensure_ascii=False, default=str)}")
            print()
    else:
        print("  (No se encontraron issues detallados en la BD)")

    print("=" * 70)
    print("\nCONCLUSIÓN:")
    if report.semaforo == "ROJO":
        print("  ❌ El archivo fue RECHAZADO por errores críticos (ver 🔴 arriba).")
        print("  Opciones:")
        print("  A) Corregir el archivo fuente y volver a subirlo.")
        print("  B) Flexibilizar las reglas en dq_service.py.")
        print("  C) Usar el endpoint con force=true para forzar la ingesta.")
    elif report.semaforo == "AMARILLO":
        print("  ⚠️  El archivo pasó con advertencias. La ingesta debió continuar.")
    else:
        print("  ✅ El archivo pasó el control de calidad sin problemas.")

finally:
    db.close()
