from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.models import get_db
from db.models_policia import PoliceAsset
from services.policia_monitor import PoliceMonitorService
from api.auth import analyst_or_admin

router = APIRouter()

@router.get("/assets", dependencies=[Depends(analyst_or_admin)])
async def get_assets(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(PoliceAsset)
    if status:
        query = query.filter(PoliceAsset.status == status.upper())
    return query.all()

@router.post("/assets/check", dependencies=[Depends(analyst_or_admin)])
async def check_updates(dataset_code: Optional[str] = None, db: Session = Depends(get_db)):
    if dataset_code:
        asset = db.query(PoliceAsset).filter(PoliceAsset.dataset_code == dataset_code.upper()).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset no encontrado")
        return await PoliceMonitorService.check_asset(db, asset)
    
    return await PoliceMonitorService.check_all_assets(db)

@router.post("/assets/seed", dependencies=[Depends(analyst_or_admin)])
async def seed_assets(db: Session = Depends(get_db)):
    count = PoliceMonitorService.seed_initial_assets(db)
    return {"message": f"Se descubrieron y registraron {count} activos de la Policía"}

@router.get("/assets/{dataset_code}", dependencies=[Depends(analyst_or_admin)])
async def get_asset(dataset_code: str, db: Session = Depends(get_db)):
    asset = db.query(PoliceAsset).filter(PoliceAsset.dataset_code == dataset_code.upper()).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return asset
