from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db.models import get_db, Event, EventType
from datetime import date
from typing import Optional, List

router = APIRouter()

POBLACION_JAMUNDI = 150000

@router.get("/estadisticas/kpis")
def get_dashboard_kpis(db: Session = Depends(get_db)):
    """
    Retorna los KPIs principales para las tarjetas del dashboard.
    """
    total = db.query(Event).count()
    homicidios = db.query(Event).join(EventType).filter(EventType.category == "HOMICIDIO").count()
    tasa = round((homicidios / POBLACION_JAMUNDI) * 100000, 2)
    
    # Zonas críticas (Barrios con más de 10 incidentes)
    zonas_criticas = db.query(Event.barrio).group_by(Event.barrio).having(func.count(Event.id) > 10).count()
    
    return {
        "total_incidentes": total,
        "tasa_homicidios": tasa,
        "zonas_criticas": zonas_criticas,
        "poblacion": POBLACION_JAMUNDI
    }

@router.get("/estadisticas/tendencia")
def get_tendencia_delictiva(db: Session = Depends(get_db)):
    """
    Retorna la tendencia mensual de delitos (Homicidios vs Otros).
    """
    # Usamos date_trunc para agrupar por mes (PostgreSQL)
    select_stmt = text("""
        SELECT 
            TO_CHAR(date_trunc('month', occurrence_date), 'Mon') as mes,
            COUNT(*) FILTER (WHERE et.category = 'HOMICIDIO') as homicidios,
            COUNT(*) FILTER (WHERE et.category != 'HOMICIDIO') as otros,
            date_trunc('month', occurrence_date) as full_date
        FROM events e
        JOIN event_types et ON e.event_type_id = et.id
        GROUP BY 1, 4
        ORDER BY 4 ASC
        LIMIT 6
    """)
    
    results = db.execute(select_stmt).fetchall()
    
    return [
        {"name": r.mes, "homicidios": r.homicidios, "hurtos": r.otros} 
        for r in results
    ]

@router.get("/estadisticas/distribucion")
def get_distribucion_delitos(db: Session = Depends(get_db)):
    """
    Retorna la distribución por tipo de delito para el gráfico de torta.
    """
    results = db.query(
        EventType.category,
        func.count(Event.id).label('total')
    ).join(Event).group_by(EventType.category).order_by(text('total DESC')).all()
    
    return [{"name": r.category, "value": r.total} for r in results]

@router.get("/estadisticas/barrios")
def get_top_barrios(db: Session = Depends(get_db)):
    """
    Retorna el Top 5 de barrios con más delitos.
    """
    results = db.query(
        Event.barrio,
        func.count(Event.id).label('total')
    ).group_by(Event.barrio).order_by(text('total DESC')).limit(5).all()
    
    return [{"name": r.barrio or "Desconocido", "delitos": r.total} for r in results]

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
        func.ST_X(text('location_geom::geometry')).label('lng'),
        func.ST_Y(text('location_geom::geometry')).label('lat')
    ).join(EventType).filter(text('location_geom IS NOT NULL'))
    
    if start_date:
        query = query.filter(Event.occurrence_date >= start_date)
    if end_date:
        query = query.filter(Event.occurrence_date <= end_date)
    
    if categories:
        conditions = []
        for cat in categories:
            conditions.append(EventType.category.ilike(f"%{cat}%"))
        query = query.filter(text(' OR '.join([f"event_types.category ILIKE '%{cat}%'" for cat in categories])))
        # Re-escritura más segura con SQLAlchemy
        from sqlalchemy import or_
        query = query.filter(or_(*[EventType.category.ilike(f"%{cat}%") for cat in categories]))
        
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
