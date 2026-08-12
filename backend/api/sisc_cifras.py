from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db
from services.sisc_cifras_service import SiscCifrasService

router = APIRouter()


class GenerateSiscCifrasRequest(BaseModel):
    edition_type: str = Field(default="weekly")
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    comparison_mode: str = Field(default="auto")
    source_codes: Optional[List[str]] = None
    max_insights: int = Field(default=5, ge=3, le=6)
    save_history: bool = True


@router.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
):
    return SiscCifrasService.source_registry(db)


@router.post("/generate")
def generate_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return SiscCifrasService.generate_publication(
        db,
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        comparison_mode=payload.comparison_mode,
        source_codes=payload.source_codes,
        max_insights=payload.max_insights,
        created_by=request.headers.get("x-sisc-user") or "local",
        save_history=payload.save_history,
    )


@router.get("/publications")
def list_publications(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return SiscCifrasService.list_publications(db, limit=limit)
