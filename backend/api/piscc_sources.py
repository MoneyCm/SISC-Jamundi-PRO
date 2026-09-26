from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import analyst_or_admin
from db.session import get_db
from services.piscc_sources_service import get_piscc_sources

router = APIRouter()


@router.get("", dependencies=[Depends(analyst_or_admin)])
def piscc_sources(cutoff: date = Query(...), db: Session = Depends(get_db)):
    return get_piscc_sources(db, cutoff)
