"""
Módulo de Analítica del SISC Jamundí.
Fuente primaria de datos: hechos_seguridad (sabanas semanales SIEDCO).
Fallback para geolocalización: tabla events (legacy).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import bindparam, func, text
from db.models import get_db, Event, EventType, User
from db.models_hechos_seguridad import HechoSeguridad
from datetime import date
from typing import Optional, List

from api.auth import get_current_user, get_optional_user, log_audit

router = APIRouter()

POBLACION_JAMUNDI = 180942

# Mapeo unificado: conducta_estandar en BD -> clave interna
CONDUCTA_KEYS = {
    'HOMICIDIO':          ['HOMICIDIO', 'Homicidio', 'HOMICIDIO INTENCIONAL', 'HOMICIDIO DOLOSO'],
    'HURTO_PERSONAS':     ['HURTO_PERSONAS', 'Hurto a personas', 'HURTO A PERSONAS'],
    'HURTO_VEHICULOS':    ['HURTO_VEHICULOS', 'HURTO_AUTOMOTORES', 'Hurto a automotores',
                           'HURTO_MOTOS', 'Hurto a motocicletas', 'HURTO A AUTOMOTORES',
                           'HURTO A MOTOCICLETAS', 'Hurto a vehículos'],
    'HURTO_COMERCIO':     ['HURTO_COMERCIO', 'Hurto a comercio', 'HURTO A COMERCIO'],
    'HURTO_RESIDENCIAS':  ['HURTO_RESIDENCIAS', 'Hurto a residencias', 'HURTO A RESIDENCIAS'],
    'LESIONES':           ['LESIONES', 'Lesiones personales', 'LESIONES PERSONALES', 'LESIONES COMUNES'],
    'EXTORSION':          ['EXTORSION', 'EXTORSIÓN', 'Extorsión'],
    'VIF':                ['VIOLENCIA INTRAFAMILIAR', 'VIOLENCIA_INTRAFAMILIAR', 'VIF',
                           'Violencia intrafamiliar'],
    'SECUESTRO':          ['SECUESTRO', 'SECUESTRO EXTORSIVO', 'Secuestro'],
    'TRAFICO':            ['TRAFICO DE ESTUPEFACIENTES', 'TRÁFICO DE ESTUPEFACIENTES',
                           'INCAUTACIÓN DE COCAINA', 'INCAUTACIÓN DE MARIHUANA'],
}


def _hechos_count(db: Session, conductas: list, start: date = None, end: date = None) -> int:
    q = db.query(func.count(HechoSeguridad.id)).filter(
        HechoSeguridad.conducta_estandar.in_(conductas)
    )
    if start:
        q = q.filter(HechoSeguridad.fecha_evento >= start)
    if end:
        q = q.filter(HechoSeguridad.fecha_evento <= end)
    return q.scalar() or 0


def _hechos_total(db: Session, start: date = None, end: date = None) -> int:
    q = db.query(func.count(HechoSeguridad.id))
    if start:
        q = q.filter(HechoSeguridad.fecha_evento >= start)
    if end:
        q = q.filter(HechoSeguridad.fecha_evento <= end)
    return q.scalar() or 0


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@router.get("/estadisticas/kpis")
def get_dashboard_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    fuente: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """KPIs del dashboard — fuente: hechos_seguridad (sabanas SIEDCO)."""
    try:
        total = _hechos_total(db, start_date, end_date)

        homicidios    = _hechos_count(db, CONDUCTA_KEYS['HOMICIDIO'],        start_date, end_date)
        hurto_pers    = _hechos_count(db, CONDUCTA_KEYS['HURTO_PERSONAS'],   start_date, end_date)
        hurto_veh     = _hechos_count(db, CONDUCTA_KEYS['HURTO_VEHICULOS'],  start_date, end_date)
        hurto_com     = _hechos_count(db, CONDUCTA_KEYS['HURTO_COMERCIO'],   start_date, end_date)
        hurto_res     = _hechos_count(db, CONDUCTA_KEYS['HURTO_RESIDENCIAS'],start_date, end_date)
        lesiones      = _hechos_count(db, CONDUCTA_KEYS['LESIONES'],         start_date, end_date)
        extorsion     = _hechos_count(db, CONDUCTA_KEYS['EXTORSION'],        start_date, end_date)
        vif           = _hechos_count(db, CONDUCTA_KEYS['VIF'],              start_date, end_date)
        secuestro     = _hechos_count(db, CONDUCTA_KEYS['SECUESTRO'],        start_date, end_date)
        trafico       = _hechos_count(db, CONDUCTA_KEYS['TRAFICO'],          start_date, end_date)

        tasa_homicidios = round((homicidios / POBLACION_JAMUNDI) * 100000, 2)

        return {
            "total_incidentes":  total,
            "total_general":     total,
            "homicidios":        homicidios,
            "tasa_homicidios":   tasa_homicidios,
            "hurto_personas":    hurto_pers,
            "hurto_vehiculos":   hurto_veh,
            "hurto_comercio":    hurto_com,
            "hurto_residencias": hurto_res,
            "lesiones":          lesiones,
            "extorsion":         extorsion,
            "vif":               vif,
            "secuestro":         secuestro,
            "trafico":           trafico,
            "poblacion":         POBLACION_JAMUNDI,
            "fuente":            "POLICIA_SEMANAL",
        }
    except Exception as e:
        print(f"ALERTA: Error en KPI endpoint: {e}")
        return {
            "total_incidentes": 0,
            "tasa_homicidios": 0.0,
            "error_fallback": True
        }


@router.get("/estadisticas/tendencia")
def get_tendencia_delictiva(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """Tendencia mensual de delitos desde hechos_seguridad."""
    MESES_ES = {
        "Jan": "Ene", "Feb": "Feb", "Mar": "Mar", "Apr": "Abr",
        "May": "May", "Jun": "Jun", "Jul": "Jul", "Aug": "Ago",
        "Sep": "Sep", "Oct": "Oct", "Nov": "Nov", "Dec": "Dic"
    }

    # Determinar granularidad según el rango
    intervalo = "month"
    if start_date and end_date:
        dias = (end_date - start_date).days
        if dias <= 31:
            intervalo = "day"
        elif dias <= 120:
            intervalo = "week"

    homicidio_vals = tuple(CONDUCTA_KEYS['HOMICIDIO'])

    query_str = f"""
        SELECT
            TO_CHAR(date_trunc('{intervalo}', fecha_evento), 'Mon YYYY') as etiqueta,
            COUNT(*) FILTER (WHERE conducta_estandar IN :hom_vals) as homicidios,
            COUNT(*) FILTER (WHERE conducta_estandar NOT IN :hom_vals) as otros,
            date_trunc('{intervalo}', fecha_evento) as full_date
        FROM hechos_seguridad
        WHERE 1=1
    """
    params = {"hom_vals": homicidio_vals}

    if start_date:
        query_str += " AND fecha_evento >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query_str += " AND fecha_evento <= :end_date"
        params["end_date"] = end_date

    query_str += " GROUP BY 1, 4 ORDER BY 4 DESC"

    if not start_date:
        query_str += " LIMIT 12"

    statement = text(query_str).bindparams(bindparam("hom_vals", expanding=True))
    results = db.execute(statement, params).fetchall()

    def translate_label(label):
        for en, es in MESES_ES.items():
            label = label.replace(en, es)
        return label

    trend_data = [
        {"name": translate_label(r.etiqueta), "homicidios": r.homicidios, "hurtos": r.otros}
        for r in results
    ]
    trend_data.reverse()
    return trend_data


@router.get("/estadisticas/distribucion")
def get_distribucion_delitos(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    fuente: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Distribución de los delitos por categoría desde hechos_seguridad."""
    labels = {
        'HOMICIDIO':         'HOMICIDIO',
        'HURTO_PERSONAS':    'HURTO PERSONAS',
        'HURTO_VEHICULOS':   'HURTO VEHÍCULOS',
        'HURTO_COMERCIO':    'HURTO COMERCIO',
        'HURTO_RESIDENCIAS': 'HURTO RESIDENCIAS',
        'LESIONES':          'LESIONES',
        'EXTORSION':         'EXTORSIÓN',
        'VIF':               'V. INTRAFAMILIAR',
        'SECUESTRO':         'SECUESTRO',
        'TRAFICO':           'TRÁFICO DROGAS',
    }
    total_stats = []
    for key, label in labels.items():
        count = _hechos_count(db, CONDUCTA_KEYS[key], start_date, end_date)
        if count > 0:
            total_stats.append({"name": label, "value": count})

    total_stats.sort(key=lambda x: x['value'], reverse=True)
    return total_stats


@router.get("/estadisticas/barrios")
def get_top_barrios(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Top 10 barrios con más delitos."""
    q = db.query(
        HechoSeguridad.barrio_normalizado.label('barrio'),
        func.count(HechoSeguridad.id).label('total')
    ).filter(
        HechoSeguridad.barrio_normalizado != '',
        HechoSeguridad.barrio_normalizado.isnot(None)
    )
    if start_date:
        q = q.filter(HechoSeguridad.fecha_evento >= start_date)
    if end_date:
        q = q.filter(HechoSeguridad.fecha_evento <= end_date)

    results = q.group_by(HechoSeguridad.barrio_normalizado)\
               .order_by(text('total DESC')).limit(10).all()

    return [{"name": r.barrio or "Desconocido", "delitos": r.total} for r in results]


@router.get("/estadisticas/resumen")
def get_resumen_estadistico(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Últimos 50 hechos para el feed de actividad reciente del dashboard."""
    q = db.query(HechoSeguridad).order_by(HechoSeguridad.fecha_evento.desc())
    if start_date:
        q = q.filter(HechoSeguridad.fecha_evento >= start_date)
    if end_date:
        q = q.filter(HechoSeguridad.fecha_evento <= end_date)

    hechos = q.limit(50).all()

    result = []
    for h in hechos:
        tipo = h.conducta_estandar or h.conducta_original or "Sin clasificar"
        # Normalizar el tipo para que el frontend lo muestre bien
        tipo_map = {
            'HURTO_PERSONAS': 'HURTO', 'HURTO_MOTOS': 'HURTO',
            'HURTO_AUTOMOTORES': 'HURTO', 'HURTO_COMERCIO': 'HURTO',
            'HURTO_RESIDENCIAS': 'HURTO',
        }
        tipo_display = tipo_map.get(tipo, tipo)

        desc_parts = []
        if h.conducta_original:
            desc_parts.append(f"[{h.conducta_original}]")
        if h.modalidad:
            desc_parts.append(h.modalidad)
        if h.arma_medio:
            desc_parts.append(h.arma_medio)
        if h.sexo and h.edad:
            desc_parts.append(f"(Víctima: {h.sexo}, {h.edad} años)")

        result.append({
            "id":          str(h.id),
            "fecha":       str(h.fecha_evento),
            "tipo":        tipo_display,
            "barrio":      h.barrio_normalizado or h.barrio_original or "Sin especificar",
            "descripcion": " - ".join(desc_parts),
            "estado":      "Abierto",
        })

    return result


@router.get("/homicidios/tasa")
def get_tasa_homicidios(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Tasa de homicidios por cada 100k habitantes."""
    conteo = _hechos_count(db, CONDUCTA_KEYS['HOMICIDIO'], start_date, end_date)
    tasa = (conteo / POBLACION_JAMUNDI) * 100000

    return {
        "categoria":          "HOMICIDIO",
        "total_eventos":      conteo,
        "tasa_por_100k":      round(tasa, 2),
        "periodo": {
            "inicio": start_date if start_date else "Histórico",
            "fin":    end_date if end_date else "Actual"
        },
        "poblacion_referencia": POBLACION_JAMUNDI
    }


@router.get("/estadisticas/comparativa")
def get_comparativa_periodos(
    start1: date,
    end1: date,
    start2: date,
    end2: date,
    fuente: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Compara dos períodos de tiempo."""
    def get_stats(s, e):
        homicidios = _hechos_count(db, CONDUCTA_KEYS['HOMICIDIO'], s, e)
        otros      = _hechos_total(db, s, e) - homicidios
        return {"homicidios": homicidios, "otros": max(0, otros), "total": _hechos_total(db, s, e)}

    def pct(p1, p2):
        if p2 == 0: return 100 if p1 > 0 else 0
        return round(((p1 - p2) / p2) * 100, 1)

    p1 = get_stats(start1, end1)
    p2 = get_stats(start2, end2)

    return {
        "periodo_actual":    p1,
        "periodo_anterior":  p2,
        "cambios_porcentaje": {
            "homicidios": pct(p1["homicidios"], p2["homicidios"]),
            "otros":      pct(p1["otros"],      p2["otros"]),
            "total":      pct(p1["total"],      p2["total"]),
        }
    }


@router.get("/eventos/geojson")
async def get_eventos_geojson(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    GeoJSON para el mapa. Usa la tabla events (legacy) porque tiene coordenadas PostGIS.
    La tabla hechos_seguridad no tiene geolocalización aún.
    """
    data_level = current_user.data_level_max if current_user else 1
    is_institutional = data_level >= 2

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
        from sqlalchemy import or_
        query = query.filter(or_(*[EventType.category.ilike(f"%{cat}%") for cat in categories]))

    result = query.order_by(Event.occurrence_date.desc()).limit(2000).all()

    features = []
    import random
    for row in result:
        lng, lat = row.lng, row.lat
        descripcion = row.descripcion

        if not is_institutional:
            lng += random.uniform(-0.0005, 0.0005)
            lat += random.uniform(-0.0005, 0.0005)
            descripcion = "Detalle reservado (Modo Abierto)"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "id":          str(row.id) if is_institutional else "HIDDEN",
                "fecha":       str(row.occurrence_date),
                "categoria":   row.category,
                "subcategoria": row.subcategory,
                "barrio":      row.barrio,
                "descripcion": descripcion,
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "mode": "Institutional" if is_institutional else "Public"
    }


@router.get("/estadisticas/ultima-actualizacion")
def get_ultima_fecha_datos(db: Session = Depends(get_db)):
    """
    Rango de datos disponible — usa hechos_seguridad como fuente.
    """
    stats = db.query(
        func.min(HechoSeguridad.fecha_evento).label("min_date"),
        func.max(HechoSeguridad.fecha_evento).label("max_date"),
        func.count(HechoSeguridad.id).label("total")
    ).first()

    return {
        "fecha_inicial": stats.min_date if stats.min_date else date.today(),
        "ultima_fecha":  stats.max_date if stats.max_date else date.today(),
        "total_hechos":  stats.total or 0,
        "fuente":        "POLICIA_SEMANAL",
    }


@router.get("/estadisticas/por-semana")
def get_por_semana(
    anio: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Hechos agrupados por semana del año para análisis temporal."""
    q = db.query(
        HechoSeguridad.semana_num.label('semana'),
        func.extract('year', HechoSeguridad.fecha_evento).label('anio'),
        func.count(HechoSeguridad.id).label('total'),
        func.count(HechoSeguridad.id).filter(
            HechoSeguridad.conducta_estandar.in_(CONDUCTA_KEYS['HOMICIDIO'])
        ).label('homicidios')
    ).filter(HechoSeguridad.semana_num.isnot(None))

    if anio:
        q = q.filter(func.extract('year', HechoSeguridad.fecha_evento) == anio)

    results = q.group_by(
        HechoSeguridad.semana_num,
        func.extract('year', HechoSeguridad.fecha_evento)
    ).order_by(text('anio, semana')).all()

    return [
        {"semana": r.semana, "anio": int(r.anio), "total": r.total, "homicidios": r.homicidios}
        for r in results
    ]


@router.get("/estadisticas/por-zona")
def get_por_zona(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Distribución de hechos por zona (urbana/rural/corregimiento)."""
    q = db.query(
        HechoSeguridad.zona.label('zona'),
        func.count(HechoSeguridad.id).label('total')
    ).filter(HechoSeguridad.zona != '', HechoSeguridad.zona.isnot(None))

    if start_date:
        q = q.filter(HechoSeguridad.fecha_evento >= start_date)
    if end_date:
        q = q.filter(HechoSeguridad.fecha_evento <= end_date)

    results = q.group_by(HechoSeguridad.zona).order_by(text('total DESC')).all()
    return [{"zona": r.zona, "total": r.total} for r in results]
