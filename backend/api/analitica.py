"""
MÃ³dulo de AnalÃ­tica del SISC JamundÃ­.
Fuente primaria de datos: hechos_seguridad (sabanas semanales SIEDCO).
Fallback para geolocalizaciÃ³n: tabla events (legacy).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import bindparam, func, or_, text
from db.models import get_db, Event, EventType, User
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow
from services.hechos_metrics import (
    canonical_hecho_key,
    hechos_sin_id_expr,
    hechos_unicos_expr,
    registros_expr,
    victimas_identificables_expr,
)
import os
from datetime import date
from typing import Optional, List

from api.auth import get_current_user, get_optional_user, log_audit

router = APIRouter()

POBLACION_JAMUNDI = 180942
PUBLIC_MAP_MIN_LOCATION_COUNT = int(os.getenv("SISC_PUBLIC_MIN_LOCATION_COUNT", "1"))

# Mapeo unificado: conducta_estandar en BD -> clave interna
CONDUCTA_KEYS = {
    'HOMICIDIO':          ['HOMICIDIO', 'Homicidio', 'HOMICIDIO INTENCIONAL', 'HOMICIDIO DOLOSO'],
    'HURTO_PERSONAS':     ['HURTO_PERSONAS', 'Hurto a personas', 'HURTO A PERSONAS'],
    'HURTO_VEHICULOS':    ['HURTO_VEHICULOS', 'HURTO_AUTOMOTORES', 'Hurto a automotores',
                           'HURTO_MOTOS', 'Hurto a motocicletas', 'HURTO A AUTOMOTORES',
                           'HURTO A MOTOCICLETAS', 'Hurto a vehÃ­culos'],
    'HURTO_COMERCIO':     ['HURTO_COMERCIO', 'Hurto a comercio', 'HURTO A COMERCIO'],
    'HURTO_RESIDENCIAS':  ['HURTO_RESIDENCIAS', 'Hurto a residencias', 'HURTO A RESIDENCIAS'],
    'LESIONES':           ['LESIONES', 'Lesiones personales', 'LESIONES PERSONALES', 'LESIONES COMUNES'],
    'EXTORSION':          ['EXTORSION', 'EXTORSIÃ“N', 'ExtorsiÃ³n'],
    'VIF':                ['VIOLENCIA INTRAFAMILIAR', 'VIOLENCIA_INTRAFAMILIAR', 'VIF',
                           'Violencia intrafamiliar'],
    'SECUESTRO':          ['SECUESTRO', 'SECUESTRO EXTORSIVO', 'Secuestro'],
    'TRAFICO':            ['TRAFICO DE ESTUPEFACIENTES', 'TRÃFICO DE ESTUPEFACIENTES',
                           'INCAUTACIÃ“N DE COCAINA', 'INCAUTACIÃ“N DE MARIHUANA'],
}


def _latest_snapshot_id(db: Session):
    row = db.query(SabanaSnapshotRow.ingestion_id).join(
        IngestionRun, IngestionRun.id == SabanaSnapshotRow.ingestion_id
    ).filter(
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).order_by(IngestionRun.fecha_fin.desc(), IngestionRun.fecha_inicio.desc()).first()
    return row[0] if row else None



def _latest_public_source(db: Session):
    run = db.query(IngestionRun).filter(
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).order_by(IngestionRun.fecha_fin.desc(), IngestionRun.fecha_inicio.desc()).first()
    return {
        "snapshot_id": None,
        "run": run,
        "source_table": "hechos_seguridad",
        "identity_expr": "COALESCE(NULLIF(BTRIM(id_fuente), ''), NULLIF(BTRIM(fingerprint), ''), id::text)",
        "date_col": "fecha_evento",
        "conducta_col": "conducta_estandar",
        "location_expr": "COALESCE(NULLIF(BTRIM(barrio_normalizado), ''), NULLIF(BTRIM(vereda_normalizada), ''), NULLIF(BTRIM(corregimiento), ''), 'SIN DATO')",
        "zone_expr": "COALESCE(NULLIF(BTRIM(zona), ''), CASE WHEN NULLIF(BTRIM(vereda_normalizada), '') IS NOT NULL OR NULLIF(BTRIM(corregimiento), '') IS NOT NULL THEN 'RURAL' ELSE 'URBANA' END)",
        "snapshot_filter": " AND fuente_codigo = 'POLICIA_SEMANAL'",
    }


def _public_count(db: Session, source: dict, start: date, end: date) -> int:
    params = {"start": start, "end": end}
    if source["snapshot_id"]:
        params["snapshot_id"] = source["snapshot_id"]
    row = db.execute(text(f"""
        SELECT COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
    """), params).first()
    return row.total or 0


def _pct_change(current: int, previous: int) -> Optional[float]:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)

def _hechos_count(db: Session, conductas: list, start: date = None, end: date = None) -> int:
    q = db.query(hechos_unicos_expr()).filter(
        HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL",
        HechoSeguridad.conducta_estandar.in_(conductas),
    )
    if start:
        q = q.filter(HechoSeguridad.fecha_evento >= start)
    if end:
        q = q.filter(HechoSeguridad.fecha_evento <= end)
    return q.scalar() or 0

def _hechos_total(db: Session, start: date = None, end: date = None) -> int:
    q = db.query(hechos_unicos_expr()).filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL")
    if start:
        q = q.filter(HechoSeguridad.fecha_evento >= start)
    if end:
        q = q.filter(HechoSeguridad.fecha_evento <= end)
    return q.scalar() or 0

def _volumen_fuente(db: Session, start: date = None, end: date = None) -> dict:
    q = db.query(
        registros_expr().label("registros"),
        victimas_identificables_expr().label("victimas_identificables"),
        hechos_sin_id_expr().label("registros_sin_id_fuente"),
    ).filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL")
    if start:
        q = q.filter(HechoSeguridad.fecha_evento >= start)
    if end:
        q = q.filter(HechoSeguridad.fecha_evento <= end)
    row = q.one()
    return {
        "registros": row.registros or 0,
        "victimas_identificables": row.victimas_identificables or 0,
        "registros_sin_id_fuente": row.registros_sin_id_fuente or 0,
    }



# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ENDPOINTS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/public/dashboard")
def get_public_dashboard(
    response: Response,
    year: Optional[int] = None,
    min_location_count: int = Query(PUBLIC_MAP_MIN_LOCATION_COUNT, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Dashboard ciudadano: solo datos agregados, anonimizados y trazables."""
    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"
    source = _latest_public_source(db)
    params = {}
    if source["snapshot_id"]:
        params["snapshot_id"] = source["snapshot_id"]

    latest_row = db.execute(text(f"""
        SELECT MIN({source['date_col']}) AS min_date, MAX({source['date_col']}) AS max_date
        FROM {source['source_table']}
        WHERE 1=1 {source['snapshot_filter']}
    """), params).first()

    max_date = latest_row.max_date if latest_row and latest_row.max_date else date.today()
    min_date = latest_row.min_date if latest_row and latest_row.min_date else date(max_date.year, 1, 1)
    target_year = year or max_date.year
    year_start = date(target_year, 1, 1)
    year_end = min(max_date, date(target_year, 12, 31)) if target_year == max_date.year else date(target_year, 12, 31)

    # La vista principal siempre usa el ano del corte. La cobertura historica se informa aparte.
    period_start = year_start
    period_end = year_end
    previous_start = date(target_year - 1, 1, 1)
    try:
        previous_end = date(target_year - 1, year_end.month, year_end.day)
    except ValueError:
        previous_end = date(target_year - 1, year_end.month, year_end.day - 1)

    base_params = {"start": period_start, "end": period_end}
    if source["snapshot_id"]:
        base_params["snapshot_id"] = source["snapshot_id"]

    total_actual = _public_count(db, source, period_start, period_end)
    total_current_year = _public_count(db, source, year_start, year_end)
    total_prev = _public_count(db, source, previous_start, previous_end)

    volume_row = db.execute(text(f"""
        SELECT COUNT(*) AS registros
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
    """), base_params).first()

    hom_vals = tuple(CONDUCTA_KEYS['HOMICIDIO'])
    hom_stmt = text(f"""
        SELECT COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        AND {source['conducta_col']} IN :hom_vals
        {source['snapshot_filter']}
    """).bindparams(bindparam("hom_vals", expanding=True))
    homicidios = db.execute(hom_stmt, {**base_params, "hom_vals": hom_vals}).first().total or 0
    tasa_homicidios = round((homicidios / POBLACION_JAMUNDI) * 100000, 2)

    monthly = db.execute(text(f"""
        SELECT TO_CHAR(date_trunc('month', {source['date_col']}), 'YYYY-MM') AS bucket,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1, date_trunc('month', {source['date_col']})
        ORDER BY date_trunc('month', {source['date_col']})
    """), base_params).fetchall()

    weekly = db.execute(text(f"""
        SELECT EXTRACT(WEEK FROM {source['date_col']})::int AS semana,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY 1
    """), base_params).fetchall()

    conductas = db.execute(text(f"""
        SELECT COALESCE(NULLIF(BTRIM({source['conducta_col']}), ''), 'SIN CLASIFICAR') AS name,
               COUNT(DISTINCT {source['identity_expr']}) AS value
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY value DESC, name ASC
        LIMIT 12
    """), base_params).fetchall()

    zones = db.execute(text(f"""
        SELECT UPPER({source['zone_expr']}) AS zona,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY total DESC
    """), base_params).fetchall()

    raw_locations = db.execute(text(f"""
        SELECT UPPER({source['location_expr']}) AS name,
               COUNT(DISTINCT {source['identity_expr']}) AS total,
               STRING_AGG(DISTINCT UPPER(COALESCE({source['zone_expr']}, 'SIN DATO')), '|') AS zones,
               STRING_AGG(DISTINCT UPPER(COALESCE({source['conducta_col']}, 'SIN CLASIFICAR')), '|') AS conductas
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY total DESC, name ASC
        LIMIT 60
    """), base_params).fetchall()

    from services.geocoding_service import GeocodingService
    suppressed_locations = 0
    territories = []
    map_points = []
    unmapped_locations = 0
    unmapped_locations_list = []
    def pending_reason(name):
        normalized = (name or '').upper()
        if '/' in normalized or normalized.startswith('VIA ') or ' VIA ' in normalized:
            return 'corredor o referencia vial'
        if 'ALFAGUARA' in normalized or 'BONANZA' in normalized:
            return 'nombre ambiguo; requiere homologacion territorial'
        return 'pendiente de homologacion o poligono oficial'

    def split_values(value):
        return [item for item in (value or '').split('|') if item]

    for row in raw_locations:
        if not row.name or row.name == "SIN DATO":
            continue
        if row.total < min_location_count:
            suppressed_locations += row.total
            unmapped_locations_list.append({"name": row.name, "total": row.total, "reason": "baja frecuencia"})
            continue
        item = {"name": row.name, "total": row.total, "zones": split_values(row.zones), "conductas": split_values(row.conductas)}
        territories.append(item)
        territory = GeocodingService.get_official_territory(row.name)
        if territory:
            lat, lng = territory["coords"]
            map_points.append({
                "name": row.name,
                "total": row.total,
                "lat": lat,
                "lng": lng,
                "geometry": territory["geometry"],
                "source": territory.get("source", "cartografia oficial"),
                "zones": item["zones"],
                "conductas": item["conductas"],
            })
        else:
            unmapped_locations += 1
            unmapped_locations_list.append({"name": row.name, "total": row.total, "reason": pending_reason(row.name), "zones": item["zones"], "conductas": item["conductas"]})

    run = source["run"]
    report_start = period_start.isoformat()
    report_end = period_end.isoformat()
    bulletin_url = f"/api/reportes/generar-boletin?fuente=POLICIA_SEMANAL&fecha_inicio={report_start}&fecha_fin={report_end}"

    return {
        "metadata": {
            "source": "SABANA SIEDCO/PONAL - Policia Nacional",
            "basis": "BASE_MAESTRA_CONSOLIDADA",
            "period_start": report_start,
            "period_end": report_end,
            "latest_event_date": max_date.isoformat(),
            "first_available_date": min_date.isoformat(),
            "year": target_year,
            "scope": "YEAR_TO_DATE" if year is None else "YEAR_FILTER",
            "comparison_start": year_start.isoformat(),
            "comparison_end": year_end.isoformat(),
            "population": POBLACION_JAMUNDI,
            "privacy": "Publicacion agregada. No incluye nombres, identificadores, telefonos, descripciones individuales, direcciones exactas ni coordenadas puntuales.",
            "methodology": "Cada sabana oficial se valida y se conserva como evidencia. La publicacion ciudadana usa una base maestra consolidada: las entregas mas recientes actualizan hechos ya existentes y las entregas historicas completan hechos distintos. El mapa solo ubica territorios con poligono oficial verificado, mediante un punto interior de ese poligono; los demas se conservan en las tablas sin ubicacion cartografica.",
            "last_ingestion": {
                "id": str(run.id) if run else None,
                "filename": run.filename if run else None,
                "loaded_at": run.fecha_fin.isoformat() if run and run.fecha_fin else None,
                "loaded_by": run.usuario_carga if run else None,
                "rows": run.total_filas if run else None,
                "approved": run.aprobadas if run else None,
                "rejected": run.rechazadas if run else None,
                "duplicates": run.duplicadas if run else None,
            },
            "downloads": [
                {"label": "Boletin tecnico PDF", "url": bulletin_url, "type": "pdf"},
            ],
        },
        "kpis": {
            "total_hechos": total_actual,
            "total_registros": volume_row.registros or 0,
            "homicidios": homicidios,
            "tasa_homicidios": tasa_homicidios,
            "previous_total": total_prev,
            "variation_pct": _pct_change(total_current_year, total_prev),
        },
        "interannual": {
            "current": {"year": target_year, "total": total_current_year, "start": year_start.isoformat(), "end": year_end.isoformat()},
            "previous": {"year": target_year - 1, "total": total_prev, "start": previous_start.isoformat(), "end": previous_end.isoformat()},
            "variation_pct": _pct_change(total_current_year, total_prev),
        },
        "monthly_trend": [{"name": row.bucket, "total": row.total} for row in monthly],
        "weekly_trend": [{"name": f"S{row.semana:02d}", "semana": row.semana, "total": row.total} for row in weekly],
        "conductas": [{"name": row.name, "value": row.value} for row in conductas],
        "zones": [{"name": row.zona or "SIN DATO", "value": row.total} for row in zones],
        "territories": territories[:20],
        "map": {
            "type": "official_territory_polygons",
            "min_location_count": min_location_count,
            "suppressed_count": suppressed_locations,
            "unmapped_count": unmapped_locations,
            "unmapped_names": unmapped_locations_list,
            "geography_source": "Polígonos oficiales urbanos y rurales: visor geográfico de la Gobernación del Valle del Cauca y capa rural R_VEREDA de Jamundí",
            "points": map_points,
        },
    }


@router.get("/estadisticas/kpis")
def get_dashboard_kpis(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    categories: Optional[List[str]] = Query(None),
    fuente: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """KPIs del dashboard â€” fuente: hechos_seguridad (sabanas SIEDCO)."""
    try:
        snapshot_id = _latest_snapshot_id(db)
        total = _hechos_total(db, start_date, end_date)
        volumen = _volumen_fuente(db, start_date, end_date)

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
            "total_hechos":      total,
            "total_registros":   volumen["registros"],
            "victimas_identificables": volumen["victimas_identificables"],
            "registros_sin_id_fuente": volumen["registros_sin_id_fuente"],
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
            "fuente":            "SABANA_SNAPSHOT" if snapshot_id else "POLICIA_SEMANAL",
            "base_conteo":       "ULTIMA_ENTREGA_SEMANAL" if snapshot_id else "CONSOLIDADO_LEGACY",
            "snapshot_id":       str(snapshot_id) if snapshot_id else None,
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

    # Determinar granularidad segÃºn el rango
    intervalo = "month"
    if start_date and end_date:
        dias = (end_date - start_date).days
        if dias <= 31:
            intervalo = "day"
        elif dias <= 120:
            intervalo = "week"

    homicidio_vals = tuple(CONDUCTA_KEYS['HOMICIDIO'])

    snapshot_id = None
    source_table = "hechos_seguridad"
    identity_expr = "COALESCE(NULLIF(BTRIM(id_fuente), ''), NULLIF(BTRIM(fingerprint), ''), id::text)"

    query_str = f"""
        SELECT
            TO_CHAR(date_trunc('{intervalo}', fecha_evento), 'Mon YYYY') as etiqueta,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar IN :hom_vals) as homicidios,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar NOT IN :hom_vals) as otros,
            date_trunc('{intervalo}', fecha_evento) as full_date
        FROM {source_table}
        WHERE 1=1
        AND fuente_codigo = 'POLICIA_SEMANAL'
    """
    params = {"hom_vals": homicidio_vals}

    if snapshot_id:
        query_str += " AND ingestion_id = :snapshot_id"
        params["snapshot_id"] = snapshot_id

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
    """DistribuciÃ³n de los delitos por categorÃ­a desde hechos_seguridad."""
    labels = {
        'HOMICIDIO':         'HOMICIDIO',
        'HURTO_PERSONAS':    'HURTO PERSONAS',
        'HURTO_VEHICULOS':   'HURTO VEHÃCULOS',
        'HURTO_COMERCIO':    'HURTO COMERCIO',
        'HURTO_RESIDENCIAS': 'HURTO RESIDENCIAS',
        'LESIONES':          'LESIONES',
        'EXTORSION':         'EXTORSIÃ“N',
        'VIF':               'V. INTRAFAMILIAR',
        'SECUESTRO':         'SECUESTRO',
        'TRAFICO':           'TRÃFICO DROGAS',
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
    """Top 10 barrios con mÃ¡s delitos."""
    q = db.query(
        HechoSeguridad.barrio_normalizado.label('barrio'),
        hechos_unicos_expr().label('total')
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
    """Ãšltimos 50 hechos para el feed de actividad reciente del dashboard."""
    q = db.query(HechoSeguridad).order_by(HechoSeguridad.fecha_evento.desc())
    if start_date:
        q = q.filter(HechoSeguridad.fecha_evento >= start_date)
    if end_date:
        q = q.filter(HechoSeguridad.fecha_evento <= end_date)

    hechos = q.limit(200).all()

    result = []
    seen_hechos = set()
    for h in hechos:
        key = canonical_hecho_key(h.id_fuente, h.fingerprint, h.id)
        if key in seen_hechos:
            continue
        seen_hechos.add(key)
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
            desc_parts.append(f"(VÃ­ctima: {h.sexo}, {h.edad} aÃ±os)")

        result.append({
            "id":          str(h.id),
            "fecha":       str(h.fecha_evento),
            "tipo":        tipo_display,
            "barrio":      h.barrio_normalizado or h.barrio_original or "Sin especificar",
            "descripcion": " - ".join(desc_parts),
            "estado":      "Abierto",
        })
        if len(result) == 50:
            break

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
            "inicio": start_date if start_date else "HistÃ³rico",
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
    """Compara dos perÃ­odos de tiempo."""
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
    La tabla hechos_seguridad no tiene geolocalizaciÃ³n aÃºn.
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
    """Rango publicado por la base maestra consolidada."""
    stats = db.query(
        func.min(HechoSeguridad.fecha_evento).label("min_date"),
        func.max(HechoSeguridad.fecha_evento).label("max_date"),
        hechos_unicos_expr().label("total"),
        registros_expr().label("registros")
    ).filter(HechoSeguridad.fuente_codigo == "POLICIA_SEMANAL").first()

    run = db.query(IngestionRun).filter(
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).order_by(IngestionRun.fecha_fin.desc(), IngestionRun.fecha_inicio.desc()).first()

    return {
        "fecha_inicial": stats.min_date if stats.min_date else date.today(),
        "ultima_fecha": stats.max_date if stats.max_date else date.today(),
        "total_hechos": stats.total or 0,
        "total_registros": stats.registros or 0,
        "fuente": "SABANA_SIEDCO_PONAL",
        "base_conteo": "BASE_MAESTRA_CONSOLIDADA",
        "archivo": run.filename if run else None,
        "fecha_carga": run.fecha_fin if run else None,
        "snapshot_id": None,
        "master": True,
    }

@router.get("/estadisticas/por-semana")
def get_por_semana(
    anio: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Hechos agrupados por semana del aÃ±o para anÃ¡lisis temporal."""
    q = db.query(
        HechoSeguridad.semana_num.label('semana'),
        func.extract('year', HechoSeguridad.fecha_evento).label('anio'),
        hechos_unicos_expr().label('total'),
        hechos_unicos_expr().filter(
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
    """DistribuciÃ³n de hechos por zona (urbana/rural/corregimiento)."""
    q = db.query(
        HechoSeguridad.zona.label('zona'),
        hechos_unicos_expr().label('total')
    ).filter(HechoSeguridad.zona != '', HechoSeguridad.zona.isnot(None))

    if start_date:
        q = q.filter(HechoSeguridad.fecha_evento >= start_date)
    if end_date:
        q = q.filter(HechoSeguridad.fecha_evento <= end_date)

    results = q.group_by(HechoSeguridad.zona).order_by(text('total DESC')).all()
    return [{"zona": r.zona, "total": r.total} for r in results]







