from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db, Proposal, SafetyFront, SecureReport
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, time
import uuid

router = APIRouter()

# --- Proposals ---

class ProposalCreate(BaseModel):
    title: str
    description: str
    category: str
    barrio: str
    author_name: Optional[str] = None

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

@router.get("/propuestas", response_model=List[ProposalResponse])
def get_proposals(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Proposal)
    if status:
        query = query.filter(Proposal.status == status)
    return query.order_by(Proposal.created_at.desc()).all()

# --- Safety Fronts (Frentes de Seguridad) ---

class SafetyFrontCreate(BaseModel):
    name: str
    barrio: str
    leader_name: str
    contact_phone: str

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

@router.get("/frentes", response_model=List[SafetyFrontResponse])
def get_safety_fronts(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(SafetyFront)
    if status:
        query = query.filter(SafetyFront.status == status)
    return query.order_by(SafetyFront.created_at.desc()).all()

# --- Secure Reports (Reporte Seguro) ---

class SecureReportCreate(BaseModel):
    tipo: str
    barrio: str
    fecha: str
    hora: str
    descripcion: str
    es_anonimo: bool
    nombre: Optional[str] = None
    contacto: Optional[str] = None

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
        raise HTTPException(status_code=400, detail=f"Error al crear reporte: {str(e)}")


@router.get("/admin/bandeja", response_model=dict)
def get_admin_inbox(db: Session = Depends(get_db)):
    """
    Agregador para la bandeja de entrada del administrador.
    Combina propuestas, frentes de seguridad y reportes seguros.
    """
    proposals = db.query(Proposal).order_by(Proposal.created_at.desc()).limit(15).all()
    fronts = db.query(SafetyFront).order_by(SafetyFront.created_at.desc()).limit(15).all()
    secure_reports = db.query(SecureReport).order_by(SecureReport.created_at.desc()).limit(15).all()
    
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
            "estado": "NUEVO",
            "descripcion": r.descripcion
        })
    
    # Ordenar por fecha descendente
    inbox.sort(key=lambda x: x["fecha"], reverse=True)
    
    return {"items": inbox}
