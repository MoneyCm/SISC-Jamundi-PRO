from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db.models import get_db, Event, EventType, User
from datetime import date
from typing import Optional, List

from api.auth import analyst_or_admin, get_current_user
from jose import JWTError, jwt
from core.security import SECRET_KEY, ALGORITHM

router = APIRouter()

async def get_optional_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None) # Opcional desde query para facilidad en mapas
):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except JWTError:
        return None

POBLACION_JAMUNDI = 150000

@router.get("/estadisticas/kpis")
def get_dashboard_kpis(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retorna los KPIs principales filtrados para las tarjetas del dashboard.
    """
    query = db.query(Event)
    if start_date: query = query.filter(Event.occurrence_date >= start_date)
    if end_date: query = query.filter(Event.occurrence_date <= end_date)
    if categories:
        query = query.join(EventType).filter(EventType.category.in_(categories))
    
    total = query.count()
    
    # Homicidios específicos para la tasa
    hom_query = query.join(EventType).filter(EventType.category == "HOMICIDIO")
    homicidios = hom_query.count()
    tasa = round((homicidios / POBLACION_JAMUNDI) * 100000, 2)
    
    # Zonas críticas (Barrios con más de 10 incidentes en el periodo)
    zonas_criticas_query = db.query(Event.barrio).filter(Event.id.in_(query.with_entities(Event.id))).group_by(Event.barrio).having(func.count(Event.id) > 10)
    zonas_criticas = zonas_criticas_query.count()
    
    return {
        "total_incidentes": total,
        "tasa_homicidios": tasa,
        "zonas_criticas": zonas_criticas,
        "poblacion": POBLACION_JAMUNDI
    }

@router.get("/estadisticas/tendencia")
def get_tendencia_delictiva(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retorna la tendencia mensual de delitos (Homicidios vs Otros) con filtros.
    """
    query_str = """
        SELECT 
            TO_CHAR(date_trunc('month', occurrence_date), 'Mon') as mes,
            COUNT(*) FILTER (WHERE et.category = 'HOMICIDIO') as homicidios,
            COUNT(*) FILTER (WHERE et.category != 'HOMICIDIO') as otros,
            date_trunc('month', occurrence_date) as full_date
        FROM events e
        JOIN event_types et ON e.event_type_id = et.id
        WHERE 1=1
    """
    params = {}
    if start_date:
        query_str += " AND occurrence_date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query_str += " AND occurrence_date <= :end_date"
        params["end_date"] = end_date
    if categories:
        query_str += " AND et.category IN :categories"
        params["categories"] = tuple(categories)

    query_str += " GROUP BY 1, 4 ORDER BY 4 ASC LIMIT 6"
    
    results = db.execute(text(query_str), params).fetchall()
    
    return [
        {"name": r.mes, "homicidios": r.homicidios, "hurtos": r.otros} 
        for r in results
    ]

@router.get("/estadisticas/distribucion")
def get_distribucion_delitos(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    db: Session = Depends(get_db)
):
    """
    Retorna la distribución por tipo de delito con filtros térmporales.
    """
    query = db.query(
        EventType.category,
        func.count(Event.id).label('total')
    ).join(Event)
    
    if start_date: query = query.filter(Event.occurrence_date >= start_date)
    if end_date: query = query.filter(Event.occurrence_date <= end_date)
    
    results = query.group_by(EventType.category).order_by(text('total DESC')).all()
    
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
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # Verificar si es usuario institucional
    user = None
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user = db.query(User).filter(User.username == payload.get("sub")).first()
        except:
            pass
            
    is_institutional = user is not None # Admin o Analista

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
    
    # ... filters ...
    if start_date:
        query = query.filter(Event.occurrence_date >= start_date)
    if end_date:
        query = query.filter(Event.occurrence_date <= end_date)
    
    if categories:
        from sqlalchemy import or_
        query = query.filter(or_(*[EventType.category.ilike(f"%{cat}%") for cat in categories]))
        
    result = query.all()
    
    features = []
    import random
    for row in result:
        # Modo Abierto: Ofuscar coordenadas y ocultar descripción
        lng = row.lng
        lat = row.lat
        descripcion = row.descripcion
        
        if not is_institutional:
            # Añadir ruido de ~50-100 metros para proteger privacidad
            lng += random.uniform(-0.0005, 0.0005)
            lat += random.uniform(-0.0005, 0.0005)
            descripcion = "Detalle reservado (Modo Abierto)"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "properties": {
                "id": str(row.id) if is_institutional else "HIDDEN",
                "fecha": str(row.occurrence_date),
                "categoria": row.category,
                "subcategoria": row.subcategory,
                "barrio": row.barrio,
                "descripcion": descripcion
            }
        }
        features.append(feature)
        
    return {
        "type": "FeatureCollection",
        "features": features,
        "mode": "Institutional" if is_institutional else "Public"
    }
