from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import get_optional_user, log_audit, require_role
from db.models import User
from db.session import get_db
from services.sisc_cifras_service import SiscCifrasService

router = APIRouter()
PUBLICATION_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]


class GenerateSiscCifrasRequest(BaseModel):
    edition_type: str = Field(default="weekly")
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    comparison_mode: str = Field(default="auto")
    source_codes: Optional[List[str]] = None
    max_insights: int = Field(default=5, ge=3, le=6)
    save_history: bool = False


def _can_save_publication(user: Optional[User]) -> bool:
    if user is None:
        return False
    role_codes = {role.code for role in (user.roles or [])}
    return bool(role_codes.intersection(PUBLICATION_ROLES))


@router.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
):
    return SiscCifrasService.source_registry(db)


@router.post("/generate")
async def generate_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if payload.save_history and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debe iniciar sesion para guardar un borrador institucional.",
        )
    if payload.save_history and not _can_save_publication(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su rol no permite guardar publicaciones institucionales.",
        )

    publication = SiscCifrasService.generate_publication(
        db,
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        comparison_mode=payload.comparison_mode,
        source_codes=payload.source_codes,
        max_insights=payload.max_insights,
        created_by=current_user.username if current_user else None,
        save_history=payload.save_history,
    )
    if payload.save_history:
        await log_audit(
            db,
            "SISC_CIFRAS_DRAFT_CREATED",
            actor_id=str(current_user.id),
            module="SISC_CIFRAS",
            target={
                "publication_id": publication.get("id"),
                "period_start": str(payload.period_start) if payload.period_start else None,
                "period_end": str(payload.period_end) if payload.period_end else None,
            },
            level=1,
            request=request,
        )
    return publication


@router.get("/publications")
def list_publications(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    return SiscCifrasService.list_publications(db, limit=limit)
