from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db, Proposal
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()

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
