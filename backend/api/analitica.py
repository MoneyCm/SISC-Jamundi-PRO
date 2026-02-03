from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db.models import get_db, Event, EventType
from datetime import date
from typing import Optional, List

router = APIRouter()

POBLACION_JAMUNDI = 150000

@router.get("/estadisticas/resumen")
def get_resumen_estadistico(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    db: Session = Depends(get_db)
):
    """
    Retorna un resumen de incidentes para los KPIs del dashboard.
    """
    query = db.query(Event).order_by(Event.occurrence_date.desc())
    if start_date:
        query = query.filter(Event.occurrence_date >= start_date)
    if end_date:
        query = query.filter(Event.occurrence_date <= end_date)
    
    events = query.all()
    
    # Transformar a formato esperado por el frontend
    incidents = []
    for e in events:
        incidents.append({
            "id": str(e.id),
            "fecha": str(e.occurrence_date),
            "tipo": e.event_type.category,
            "barrio": e.barrio or "Sin especificar",
            "descripcion": e.descripcion or "",
            "estado": e.estado or "Abierto"
        })
    
    return incidents

@router.get("/homicidios/tasa")
def get_tasa_homicidios(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    db: Session = Depends(get_db)
):
    """
    Calcula la tasa de homicidios por cada 100k habitantes.
    Fórmula: (Nº Homicidios / 150,000) * 100,000
    """
    query = db.query(func.count(Event.id)).join(EventType).filter(EventType.category == "HOMICIDIO")
    
    if start_date:
        query = query.filter(Event.occurrence_date >= start_date)
    if end_date:
        query = query.filter(Event.occurrence_date <= end_date)
    
    conteo = query.scalar() or 0
    tasa = (conteo / POBLACION_JAMUNDI) * 100000
    
    return {
        "categoria": "HOMICIDIO",
        "total_eventos": conteo,
        "tasa_por_100k": round(tasa, 2),
        "periodo": {
            "inicio": start_date if start_date else "Histórico",
            "fin": end_date if end_date else "Actual"
        },
        "poblacion_referencia": POBLACION_JAMUNDI
    }

@router.get("/eventos/geojson")
def get_eventos_geojson(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(
        Event.id,
        Event.occurrence_date,
        Event.barrio,
        Event.descripcion,
        EventType.category,
        EventType.subcategory,
        func.ST_X(text('location_geom')).label('lng'),
        func.ST_Y(text('location_geom')).label('lat')
    ).join(EventType).filter(text('location_geom IS NOT NULL'))
    
    if start_date:
        query = query.filter(Event.occurrence_date >= start_date)
    if end_date:
        query = query.filter(Event.occurrence_date <= end_date)
    
    if categories:
        query = query.filter(EventType.category.in_(categories))
        
    result = query.all()
    
    features = []
    for row in result:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.lng, row.lat]
            },
            "properties": {
                "id": str(row.id),
                "fecha": str(row.occurrence_date),
                "categoria": row.category,
                "subcategoria": row.subcategory,
                "barrio": row.barrio,
                "descripcion": row.descripcion
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features
    }
