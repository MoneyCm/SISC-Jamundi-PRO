from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import require_role
from db.session import get_db
from services.piscc_goals import build_goals
from services.piscc_sources_service import get_piscc_sources

router = APIRouter()

# Los mismos perfiles que ven el Boletín institucional; sin esto el PDF sale sin la página PISCC.
BULLETIN_ROLES = ["TI_ADMIN", "FUNC_ADMIN", "ANALYST", "DIRECTIVE", "SOURCE_UPLOADER", "STEWARD"]


@router.get("", dependencies=[Depends(require_role(BULLETIN_ROLES))])
def piscc_sources(cutoff: date = Query(...), source_version_id: Optional[UUID] = Query(None), db: Session = Depends(get_db)):
    # "goals" es la tabla 16 con el mismo cálculo del Centro de análisis, al corte del boletín.
    return {**get_piscc_sources(db, cutoff),
            "goals": build_goals(db, cutoff, str(source_version_id) if source_version_id else None)}
