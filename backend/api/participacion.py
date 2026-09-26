from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from db.models import get_db, Proposal, SafetyFront, SecureReport, User
from api.auth import log_audit, require_role
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date, time
import logging
import uuid

router = APIRouter()
logger = logging.getLogger("sisc_api")

# --- Proposals ---

class ProposalCreate(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=10, max_length=3000)
    category: str = Field(min_length=2, max_length=80)
    barrio: str = Field(min_length=2, max_length=120)
    author_name: Optional[str] = Field(default=None, max_length=120)

class ProposalPublicResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    category: str
    barrio: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProposalResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    category: str
    barrio: str
    status: str
    created_at: datetime
    author_name: Optional[str] = None

    class Config:
        from_attributes = True

@router.post("/propuestas", response_model=ProposalResponse)
def create_proposal(proposal: ProposalCreate, db: Session = Depends(get_db)):
    db_proposal = Proposal(
        title=proposal.title,
        description=proposal.description,
        category=proposal.category,
        barrio=proposal.barrio,
        author_name=proposal.author_name
    )
    db.add(db_proposal)
    db.commit()
    db.refresh(db_proposal)
    return db_proposal

@router.get("/propuestas", response_model=List[ProposalPublicResponse])
def get_proposals(db: Session = Depends(get_db)):
    estados_publicos = ("APROBADA", "EN_CURSO", "COMPLETADA")
    return (
        db.query(Proposal)
        .filter(Proposal.status.in_(estados_publicos))
        .order_by(Proposal.created_at.desc())
        .limit(100)
        .all()
    )

# --- Safety Fronts (Frentes de Seguridad) ---

class SafetyFrontCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    barrio: str = Field(min_length=2, max_length=120)
    leader_name: str = Field(min_length=3, max_length=120)
    contact_phone: str = Field(min_length=7, max_length=30)

class SafetyFrontPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    barrio: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SafetyFrontResponse(BaseModel):
    id: uuid.UUID
    name: str
    barrio: str
    leader_name: str
    contact_phone: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/frentes", response_model=SafetyFrontResponse)
def create_safety_front(front: SafetyFrontCreate, db: Session = Depends(get_db)):
    db_front = SafetyFront(
        name=front.name,
        barrio=front.barrio,
        leader_name=front.leader_name,
        contact_phone=front.contact_phone
    )
    db.add(db_front)
    db.commit()
    db.refresh(db_front)
    return db_front

@router.get("/frentes", response_model=List[SafetyFrontPublicResponse])
def get_safety_fronts(db: Session = Depends(get_db)):
    return (
        db.query(SafetyFront)
        .filter(SafetyFront.status == "ACTIVO")
        .order_by(SafetyFront.created_at.desc())
        .limit(100)
        .all()
    )

# --- Secure Reports (Reporte Seguro) ---

class SecureReportCreate(BaseModel):
    tipo: str = Field(min_length=2, max_length=100)
    barrio: str = Field(min_length=2, max_length=120)
    fecha: str = Field(min_length=10, max_length=10)
    hora: str = Field(min_length=5, max_length=5)
    descripcion: str = Field(min_length=10, max_length=4000)
    es_anonimo: bool
    nombre: Optional[str] = Field(default=None, max_length=120)
    contacto: Optional[str] = Field(default=None, max_length=160)

class SecureReportResponse(BaseModel):
    id: uuid.UUID
    tipo: str
    barrio: str
    fecha: date
    hora: time
    descripcion: str
    es_anonimo: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/reportes-seguros", response_model=SecureReportResponse)
def create_secure_report(report: SecureReportCreate, db: Session = Depends(get_db)):
    try:
        # Convertir strings de fecha y hora a objetos date/time
        fecha_obj = datetime.strptime(report.fecha, "%Y-%m-%d").date()
        hora_obj = datetime.strptime(report.hora, "%H:%M").time()
        
        db_report = SecureReport(
            tipo=report.tipo,
            barrio=report.barrio,
            fecha=fecha_obj,
            hora=hora_obj,
            descripcion=report.descripcion,
            es_anonimo=report.es_anonimo,
            nombre=report.nombre if not report.es_anonimo else None,
            contacto=report.contacto if not report.es_anonimo else None
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)
        return db_report
    except Exception as e:
        db.rollback()
        logger.exception("No se pudo crear el reporte ciudadano seguro")
        raise HTTPException(status_code=400, detail="No se pudo crear el reporte. Revise los datos enviados.")


@router.get("/admin/bandeja", response_model=dict)
def get_admin_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["TI_ADMIN", "FUNC_ADMIN", "ANALYST"])),
):
    """
    Agregador para la bandeja de entrada del administrador.
    Combina propuestas, frentes de seguridad y reportes seguros.
    """
    proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).limit(15).all()
    fronts = db.query(SafetyFront).order_by(SafetyFront.created_at.desc()).limit(15).all()
    # Solo los reportes que siguen abiertos: los cerrados quedan en la gestión de reportes.
    secure_reports = db.query(SecureReport).filter(SecureReport.estado != "CERRADO").order_by(
        SecureReport.created_at.desc()).limit(15).all()
    
    # Transformar a formato unificado para la UI
    inbox = []
    for p in proposals:
        inbox.append({
            "id": str(p.id),
            "tipo": "PROPUESTA",
            "titulo": p.title,
            "subtitulo": p.barrio,
            "fecha": p.created_at.isoformat(),
            "estado": p.status,
            "descripcion": p.description
        })
    for f in fronts:
        inbox.append({
            "id": str(f.id),
            "tipo": "FRENTE",
            "titulo": f.name,
            "subtitulo": f.barrio,
            "fecha": f.created_at.isoformat(),
            "estado": f.status,
            "descripcion": f"Líder: {f.leader_name} - Tel: {f.contact_phone}"
        })
    for r in secure_reports:
        inbox.append({
            "id": str(r.id),
            "tipo": "REPORTE_SEGURO",
            "titulo": r.tipo,
            "subtitulo": r.barrio,
            "fecha": r.created_at.isoformat(),
            "estado": r.estado,
            "descripcion": r.descripcion
        })
    
    # Ordenar por fecha descendente
    inbox.sort(key=lambda x: x["fecha"], reverse=True)
    
    return {"items": inbox}


# --- Atención de reportes seguros -----------------------------------------------------------

REPORT_ROLES = ["TI_ADMIN", "FUNC_ADMIN", "ANALYST", "DIRECTIVE"]
REPORT_STATES = ("RECIBIDO", "EN_GESTION", "CERRADO")
# Qué se puede hacer desde cada estado. Reabrir un cerrado exige nota, igual que cerrarlo.
REPORT_TRANSITIONS = {"RECIBIDO": {"EN_GESTION", "CERRADO"}, "EN_GESTION": {"CERRADO"}, "CERRADO": {"EN_GESTION"}}


class ReportStatusIn(BaseModel):
    estado: str
    nota: Optional[str] = Field(default=None, max_length=2000)
    expected_version: int = Field(ge=0)


def serialize_report(row: SecureReport) -> dict:
    return {
        "id": str(row.id), "tipo": row.tipo, "barrio": row.barrio,
        "fecha": row.fecha.isoformat() if row.fecha else None,
        "hora": row.hora.strftime("%H:%M") if row.hora else None,
        "descripcion": row.descripcion, "es_anonimo": bool(row.es_anonimo),
        # Datos de contacto solo si la persona los dio (no anónimo); los ve solo el equipo autorizado.
        "nombre": None if row.es_anonimo else row.nombre,
        "contacto": None if row.es_anonimo else row.contacto,
        "recibido": row.created_at.isoformat() if row.created_at else None,
        "estado": row.estado, "gestion": row.gestion or [], "atendido_por": row.atendido_por,
        "actualizado_at": row.actualizado_at.isoformat() if row.actualizado_at else None,
        "version": row.version,
    }


@router.get("/admin/reportes-seguros")
def list_secure_reports(estado: Optional[str] = Query(default=None), db: Session = Depends(get_db),
                        current_user: User = Depends(require_role(REPORT_ROLES))):
    """Reportes seguros del portal con su estado de atención; abiertos primero, del más antiguo al más nuevo."""
    query = db.query(SecureReport)
    if estado:
        if estado not in REPORT_STATES:
            raise HTTPException(422, f"Estado no válido. Use: {', '.join(REPORT_STATES)}.")
        query = query.filter(SecureReport.estado == estado)
    rows = query.all()
    order = {"RECIBIDO": 0, "EN_GESTION": 1, "CERRADO": 2}
    rows.sort(key=lambda row: (order.get(row.estado, 9), row.created_at or datetime.min))
    counts = {state: 0 for state in REPORT_STATES}
    for row in db.query(SecureReport.estado).all():
        counts[row[0]] = counts.get(row[0], 0) + 1
    return {"items": [serialize_report(row) for row in rows], "counts": counts}


@router.put("/admin/reportes-seguros/{report_id}/estado")
async def update_secure_report_status(report_id: uuid.UUID, payload: ReportStatusIn, request: Request,
                                      db: Session = Depends(get_db),
                                      current_user: User = Depends(require_role(REPORT_ROLES))):
    from datetime import timezone

    row = db.get(SecureReport, report_id)
    if not row:
        raise HTTPException(404, "El reporte no existe.")
    if row.version != payload.expected_version:
        raise HTTPException(409, "Otra persona actualizó este reporte. Recargue antes de guardar.")
    if payload.estado not in REPORT_TRANSITIONS.get(row.estado, set()):
        raise HTTPException(422, f"No se puede pasar de {row.estado} a {payload.estado}.")
    nota = (payload.nota or "").strip()
    if payload.estado == "CERRADO" and not nota:
        raise HTTPException(422, "Escriba cómo se cerró el reporte: a quién se remitió, qué se hizo o por qué no procede.")
    if row.estado == "CERRADO" and not nota:
        raise HTTPException(422, "Escriba por qué se reabre el reporte.")
    event = {"de": row.estado, "a": payload.estado, "nota": nota or None, "por": current_user.username,
             "at": datetime.now(timezone.utc).isoformat()}
    row.gestion = [*(row.gestion or []), event]
    row.estado = payload.estado
    row.atendido_por = current_user.username
    row.actualizado_at = datetime.now(timezone.utc)
    row.version += 1
    db.commit()
    db.refresh(row)
    await log_audit(db, "SECURE_REPORT_STATUS", actor_id=str(current_user.id), module="PARTICIPACION",
                    target={"report": str(row.id), "estado": row.estado}, level=2, request=request)
    return serialize_report(row)

