from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.models import get_db
from db.models_mindefensa import MindefensaAsset
from services.mindefensa_monitor import MindefensaMonitorService
from api.auth import analyst_or_admin

router = APIRouter()

@router.get("/assets", dependencies=[Depends(analyst_or_admin)])
async def get_assets(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(MindefensaAsset)
    if status:
        query = query.filter(MindefensaAsset.status == status.upper())
    return query.all()

@router.post("/assets/check", dependencies=[Depends(analyst_or_admin)])
async def check_updates(dataset_code: Optional[str] = None, db: Session = Depends(get_db)):
    if dataset_code:
        asset = db.query(MindefensaAsset).filter(MindefensaAsset.dataset_code == dataset_code.upper()).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset no encontrado")
        return await MindefensaMonitorService.check_asset(db, asset)
    
    return await MindefensaMonitorService.check_all_assets(db)

@router.post("/assets/seed", dependencies=[Depends(analyst_or_admin)])
async def seed_assets(db: Session = Depends(get_db)):
    MindefensaMonitorService.seed_initial_assets(db)
    return {"message": "Assets iniciales creados correctamente"}

@router.get("/assets/{dataset_code}", dependencies=[Depends(analyst_or_admin)])
async def get_asset(dataset_code: str, db: Session = Depends(get_db)):
    asset = db.query(MindefensaAsset).filter(MindefensaAsset.dataset_code == dataset_code.upper()).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return asset
