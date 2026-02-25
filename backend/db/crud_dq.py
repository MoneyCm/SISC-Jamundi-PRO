from sqlalchemy.orm import Session
from db.models_dq import DqReport, DqIssue
from typing import List, Optional, Dict, Any
from uuid import UUID

from datetime import datetime

def create_dq_report(db: Session, report_data: Dict[str, Any]) -> DqReport:
    # Extraer datos especiales
    issues_data = report_data.get("issues", [])
    samples_data = report_data.get("samples", {})
    profiles_data = report_data.get("profiles", {})
    
    # Crear el objeto con campos básicos
    db_report = DqReport(
        filename=report_data.get("filename") or "ARCHIVO_DESCONOCIDO",
        source_name=report_data.get("source_name"),
        rows_total=report_data.get("rows_total"),
        schema_ok=report_data.get("schema_ok", True),
        score_overall=report_data.get("score_overall"),
        score_completeness=report_data.get("score_completeness"),
        score_validity=report_data.get("score_validity"),
        score_consistency=report_data.get("score_consistency"),
        score_uniqueness=report_data.get("score_uniqueness"),
        semaforo=report_data.get("semaforo")
    )
    
    # Manejar fechas (convertir de ISO string a datetime si es necesario)
    for date_field in ["min_date", "max_date"]:
        val = report_data.get(date_field)
        if isinstance(val, str):
            try:
                setattr(db_report, date_field, datetime.fromisoformat(val))
            except:
                pass
    
    # Asignar JSONBs
    db_report.missing_cols = report_data.get("missing_cols")
    db_report.extra_cols = report_data.get("extra_cols")
    db_report.report_json = {**report_data, "profiles": profiles_data}
    db_report.sample_json = samples_data
    
    db.add(db_report)
    db.flush()
    
    # Crear los hallazgos (issues)
    for issue in issues_data:
        db_issue = DqIssue(
            report_id=db_report.id,
            severity=issue.get("severity"),
            field=issue.get("field"),
            rule=issue.get("rule"),
            count=issue.get("count", 0),
            example=issue.get("example")
        )
        db.add(db_issue)
        
    db.commit()
    db.refresh(db_report)
    return db_report

def get_dq_report(db: Session, report_id: UUID) -> Optional[DqReport]:
    return db.query(DqReport).filter(DqReport.id == report_id).first()

def list_dq_reports(db: Session, skip: int = 0, limit: int = 50) -> List[DqReport]:
    return db.query(DqReport).order_by(DqReport.created_at.desc()).offset(skip).limit(limit).all()

def list_dq_issues(db: Session, report_id: UUID, severity: str = None, field: str = None, skip: int = 0, limit: int = 100) -> List[DqIssue]:
    query = db.query(DqIssue).filter(DqIssue.report_id == report_id)
    if severity:
        query = query.filter(DqIssue.severity == severity)
    if field:
        query = query.filter(DqIssue.field == field)
    return query.offset(skip).limit(limit).all()
