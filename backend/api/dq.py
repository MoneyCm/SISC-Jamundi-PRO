from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from db.models import get_db, User
from api.auth import require_role
from services import dq_service
from db import crud_dq
from uuid import UUID
import io
import json

router = APIRouter()
DQ_ROLES = ["STEWARD", "FUNC_ADMIN", "TI_ADMIN"]

@router.post("/run")
async def run_data_quality(
    file: UploadFile = File(...),
    source_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    # Leer el archivo
    content = await file.read()
    
    # Ejecutar análisis
    report_data = dq_service.run_dq(content, file.filename, source_name)
    
    if "error" in report_data and not report_data.get("schema_ok", True):
        raise HTTPException(status_code=400, detail=report_data["error"])
        
    # Guardar en DB
    db_report = crud_dq.create_dq_report(db, report_data)
    
    return {
        "report_id": db_report.id,
        "summary": {
            "filename": db_report.filename,
            "rows_total": db_report.rows_total,
            "score_overall": db_report.score_overall,
            "issues_count": len(db_report.issues),
            "created_at": db_report.created_at
        }
    }

@router.get("/reports")
def get_reports(
    skip: int = 0, 
    limit: int = 50, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    return crud_dq.list_dq_reports(db, skip=skip, limit=limit)

@router.get("/report/{report_id}")
def get_report(
    report_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    report = crud_dq.get_dq_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return report.report_json

@router.get("/report/{report_id}/issues")
def get_issues(
    report_id: UUID,
    severity: Optional[str] = None,
    field: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    return crud_dq.list_dq_issues(db, report_id, severity, field, skip, limit)

@router.get("/report/{report_id}/json")
def download_json(
    report_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    report = crud_dq.get_dq_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    
    return Response(
        content=json.dumps(report.report_json, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=dq_report_{report_id}.json"}
    )

@router.get("/report/{report_id}/excel")
def download_excel(
    report_id: UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(DQ_ROLES)),
):
    report = crud_dq.get_dq_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    
    excel_content = dq_service.build_excel_from_report(report.report_json)
    
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=dq_report_{report_id}.xlsx"}
    )
