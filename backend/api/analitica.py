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

POBLACION_JAMUNDI = 180942

@router.get("/estadisticas/kpis")
def get_dashboard_kpis(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # 1. Total Incidentes (con filtros de fecha y categoría)
        total_q = db.query(func.count(Event.id))
        if start_date: total_q = total_q.filter(Event.occurrence_date >= start_date)
        if end_date: total_q = total_q.filter(Event.occurrence_date <= end_date)
        if categories:
            total_q = total_q.join(EventType).filter(EventType.category.in_(categories))
        total = total_q.scalar() or 0
        
        # 2. Homicidios (para la tasa)
        hom_q = db.query(func.count(Event.id)).join(EventType).filter(EventType.category == "HOMICIDIO")
        if start_date: hom_q = hom_q.filter(Event.occurrence_date >= start_date)
        if end_date: hom_q = hom_q.filter(Event.occurrence_date <= end_date)
        homicidios = hom_q.scalar() or 0
        tasa = round((homicidios / POBLACION_JAMUNDI) * 100000, 2)
        
        # 3. Zonas críticas (Barrios con > 10 incidentes)
        # Usamos una subquery explícita para contar grupos
        subq = db.query(Event.barrio).filter(Event.barrio != 'Sin especificar')
        if start_date: subq = subq.filter(Event.occurrence_date >= start_date)
        if end_date: subq = subq.filter(Event.occurrence_date <= end_date)
        if categories: subq = subq.join(EventType).filter(EventType.category.in_(categories))
        
        subq_grouped = subq.group_by(Event.barrio).having(func.count(Event.id) > 10).subquery()
        zonas_criticas = db.query(func.count()).select_from(subq_grouped).scalar() or 0
        
        return {
            "total_incidentes": total,
            "tasa_homicidios": tasa,
            "zonas_criticas": zonas_criticas,
            "poblacion": POBLACION_JAMUNDI
        }
    except Exception as e:
        # Fallback de seguridad: Nunca retornar 500 si podemos retornar data parcial
        print(f"ALERTA: Error en KPI endpoint: {str(e)}")
        return {
            "total_incidentes": total if 'total' in locals() else 0,
            "tasa_homicidios": 0.0,
            "zonas_criticas": 0,
            "poblacion": POBLACION_JAMUNDI,
            "error_fallback": True
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
    # Determinar granularidad según el rango
    intervalo = "month"
    formato_sql = "Mon"
    if start_date and end_date:
        dias = (end_date - start_date).days
        if dias <= 31:
            intervalo = "day"
            formato_sql = "DD Mon"
        elif dias <= 120:
            intervalo = "week"
            formato_sql = "DD Mon" # Inicio de semana

    query_str = f"""
        SELECT 
            TO_CHAR(date_trunc('{intervalo}', occurrence_date), '{formato_sql}') as etiqueta,
            COUNT(*) FILTER (WHERE et.category = 'HOMICIDIO') as homicidios,
            COUNT(*) FILTER (WHERE et.category != 'HOMICIDIO') as otros,
            date_trunc('{intervalo}', occurrence_date) as full_date
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

    query_str += f" GROUP BY 1, 4 ORDER BY 4 DESC"
    
    # Si NO se provee fecha inicio, limitamos a los últimos 6 meses para contexto
    if not start_date:
        query_str += " LIMIT 6"
    
    results = db.execute(text(query_str), params).fetchall()
    
    # Mapeo manual de meses a Español para evitar dependencia de locale de DB
    MESES_ES = {
        "Jan": "Ene", "Feb": "Feb", "Mar": "Mar", "Apr": "Abr", "May": "May", "Jun": "Jun",
        "Jul": "Jul", "Aug": "Ago", "Sep": "Sep", "Oct": "Oct", "Nov": "Nov", "Dec": "Dic"
    }
    
    def translate_label(label):
        for en, es in MESES_ES.items():
            if en in label:
                return label.replace(en, es)
        return label
    
    # Invertir para que se vea cronológico en el gráfico (Antiguo -> Nuevo)
    trend_data = [
        {
            "name": translate_label(r.etiqueta), 
            "homicidios": r.homicidios, 
            "hurtos": r.otros
        } 
        for r in results
    ]
    trend_data.reverse()
    
    return trend_data

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
    Fórmula: (Nº Homicidios / 180,942) * 100,000
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

@router.get("/estadisticas/comparativa")
def get_comparativa_periodos(
    start1: date, 
    end1: date, 
    start2: date, 
    end2: date,
    db: Session = Depends(get_db)
):
    """
    Compara dos periodos de tiempo seleccionados.
    Útil para comparaciones Año tras Año (YoY).
    """
    def get_stats(s, e):
        # Homicidios
        homicidios = db.query(func.count(Event.id)).join(EventType).filter(
            EventType.category == "HOMICIDIO",
            Event.occurrence_date >= s,
            Event.occurrence_date <= e
        ).scalar() or 0
        
        # Otros delitos (Hurtos, Lesiones, etc)
        otros = db.query(func.count(Event.id)).join(EventType).filter(
            EventType.category != "HOMICIDIO",
            Event.occurrence_date >= s,
            Event.occurrence_date <= e
        ).scalar() or 0
        
        return {"homicidios": homicidios, "otros": otros, "total": homicidios + otros}

    periodo1 = get_stats(start1, end1)
    periodo2 = get_stats(start2, end2)
    
    def calculate_change(p1, p2):
        if p2 == 0: return 100 if p1 > 0 else 0
        return round(((p1 - p2) / p2) * 100, 1)

    return {
        "periodo_actual": periodo1,
        "periodo_anterior": periodo2,
        "cambios_porcentaje": {
            "homicidios": calculate_change(periodo1["homicidios"], periodo2["homicidios"]),
            "otros": calculate_change(periodo1["otros"], periodo2["otros"]),
            "total": calculate_change(periodo1["total"], periodo2["total"])
        }
    }

@router.get("/eventos/geojson")
def get_eventos_geojson(
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    categories: Optional[List[str]] = Query(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # Verificar permisos de roles
    user = None
    sensitive_access = False
    
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            role_name = payload.get("role")
            # Roles que pueden ver datos sensibles (Analista, Fuerza Pública, Admin)
            if role_name in ["Administrador (Observatorio)", "Analista Institucional", "Enlace Fuerza Pública"]:
                sensitive_access = True
            user = db.query(User).filter(User.username == payload.get("sub")).first()
        except:
            pass

    is_institutional = sensitive_access

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

@router.get("/estadisticas/ultima-actualizacion")
def get_ultima_fecha_datos(db: Session = Depends(get_db)):
    """
    Retorna el rango total de datos disponibles (primera y última fecha).
    Útil para mostrar la cobertura de datos en el Dashboard.
    """
    stats = db.query(
        func.min(Event.occurrence_date).label("min_date"),
        func.max(Event.occurrence_date).label("max_date")
    ).first()
    
    return {
        "fecha_inicial": stats.min_date if stats.min_date else date.today(),
        "ultima_fecha": stats.max_date if stats.max_date else date.today()
    }
