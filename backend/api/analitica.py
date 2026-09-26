"""
Módulo de Analítica del SISC Jamundí.
Fuente primaria de datos: hechos_seguridad (sabanas semanales SIEDCO).
Fallback para geolocalización: tabla events (legacy).
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
from services.national_context_service import population_for, rate_per_100k
import csv
import hashlib
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, List
import re

from api.auth import get_current_user, get_optional_user, institutional_access, log_audit

router = APIRouter()

JAMUNDI_DANE_CODE = "76364"
PUBLIC_MAP_MIN_LOCATION_COUNT = int(os.getenv("SISC_PUBLIC_MIN_LOCATION_COUNT", "3"))


def _jamundi_population(reference_date: Optional[date]) -> Optional[int]:
    """Return the official DANE projection for the year used by the metric."""
    reference_year = (reference_date or date.today()).year
    return population_for(JAMUNDI_DANE_CODE, reference_year)

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

CONDUCTA_PUBLIC_LABELS = {
    'HOMICIDIO': 'Homicidio',
    'HURTO_PERSONAS': 'Hurto a personas',
    'HURTO_VEHICULOS': 'Hurto de vehículos y motocicletas',
    'HURTO_COMERCIO': 'Hurto a comercio',
    'HURTO_RESIDENCIAS': 'Hurto a residencias',
    'LESIONES': 'Lesiones personales',
    'EXTORSION': 'Extorsión',
    'VIF': 'Violencia intrafamiliar',
    'SECUESTRO': 'Secuestro',
    'TRAFICO': 'Tráfico de estupefacientes',
}

PUBLIC_INVALID_LOCATION_MARKERS = (
    'PENDIENTE POR ASIGNAR',
    'BARRIO PENDIENTE',
    'NO APLICA',
    'NO REPORTA',
    'SIN DATO',
    'SIN INFORMACION',
    'SIN UBICACION',
    'NAN',
)


def _sql_literal(value: str) -> str:
    """Quote trusted, server-owned lookup values used to build a CASE expression."""
    return "'" + value.replace("'", "''") + "'"


def _canonical_conducta_sql(column: str) -> str:
    branches = []
    for code, aliases in CONDUCTA_KEYS.items():
        values = sorted({alias.strip().upper() for alias in aliases})
        quoted = ', '.join(_sql_literal(value) for value in values)
        branches.append(f"WHEN UPPER(BTRIM({column})) IN ({quoted}) THEN {_sql_literal(code)}")
    return (
        "CASE "
        + " ".join(branches)
        + f" ELSE COALESCE(NULLIF(UPPER(BTRIM({column})), ''), 'SIN_CLASIFICAR') END"
    )


def _canonical_location_sql(expression: str) -> str:
    """Remove source-version suffixes that are not part of the official place name."""
    return f"REGEXP_REPLACE(UPPER({expression}), '\\s+E24$', '')"


def _public_conducta_label(code: str) -> str:
    if code in CONDUCTA_PUBLIC_LABELS:
        return CONDUCTA_PUBLIC_LABELS[code]
    if not code or code == 'SIN_CLASIFICAR':
        return 'Sin clasificar'
    return code.replace('_', ' ').strip().title()


def _is_publishable_location(name: Optional[str]) -> bool:
    normalized = (name or '').strip().upper()
    # "JAMUNDI" solo es el municipio, no un barrio o vereda publicable.
    if normalized in {'JAMUNDI', 'JAMUNDÍ'}:
        return False
    return bool(normalized) and not any(marker in normalized for marker in PUBLIC_INVALID_LOCATION_MARKERS)


def _shift_year(value: date, years: int = -1) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _comparison_period(period_start: date, period_end: date, mode: str):
    if mode == 'none':
        return None, None
    if mode == 'previous_period':
        span = (period_end - period_start).days + 1
        previous_end = period_start - timedelta(days=1)
        return previous_end - timedelta(days=span - 1), previous_end
    return _shift_year(period_start), _shift_year(period_end)


def _resolve_public_period(
    max_date: date,
    selected_year: Optional[int],
    period_mode: str,
    custom_start: Optional[date],
    custom_end: Optional[date],
):
    allowed_modes = {'year_to_date', 'last_30_days', 'last_7_days', 'custom'}
    if period_mode not in allowed_modes:
        raise HTTPException(status_code=400, detail='Periodo no soportado.')

    target_year = selected_year or max_date.year
    if period_mode == 'custom':
        if not custom_start or not custom_end:
            raise HTTPException(status_code=400, detail='El periodo personalizado requiere fecha inicial y final.')
        if custom_start > custom_end:
            raise HTTPException(status_code=400, detail='La fecha inicial no puede ser posterior a la fecha final.')
        return custom_start, custom_end, custom_end.year

    effective_end = min(max_date, date(target_year, 12, 31)) if target_year == max_date.year else date(target_year, 12, 31)
    if period_mode == 'last_30_days':
        return effective_end - timedelta(days=29), effective_end, target_year
    if period_mode == 'last_7_days':
        return effective_end - timedelta(days=6), effective_end, target_year
    return date(target_year, 1, 1), effective_end, target_year


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


def _public_count(
    db: Session,
    source: dict,
    start: date,
    end: date,
    filter_sql: str = '',
    filter_params: Optional[dict] = None,
) -> int:
    params = {"start": start, "end": end, **(filter_params or {})}
    if source["snapshot_id"]:
        params["snapshot_id"] = source["snapshot_id"]
    row = db.execute(text(f"""
        SELECT COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
    """), params).first()
    return row.total or 0


def _public_territory_name(raw_name: str) -> str:
    """Nombre ciudadano de un lugar de la sábana.

    Las variantes policiales de un mismo territorio ("CGTO POTRERITO", "POTRERITO (24-S-02)",
    "CGTO POTRERITO (24-S2-1)") se unifican en el nombre del polígono oficial ("Potrerito").
    Los lugares sin polígono conservan su nombre, sin códigos de sector y en formato título.
    """
    from services.geocoding_service import GeocodingService, _display_name

    territory = GeocodingService.get_official_territory(raw_name)
    if territory and territory.get("name"):
        return territory["name"]
    clean = re.sub(r"\s*\([^)]*\)\s*$", "", str(raw_name or "")).strip()
    clean = re.sub(r"^(CGTO|CORREGIMIENTO)\s+", "", clean)
    clean = re.sub(r"\s+E\d+$", "", clean)
    if not clean:
        return str(raw_name or "")
    display = _display_name(clean)
    return re.sub(r"^Via\b", "Vía", display)


def _public_territory_catalog(db: Session, source: dict) -> Dict[str, str]:
    """Mapa nombre crudo (canónico) -> nombre ciudadano, para todos los lugares de la fuente."""
    location = _canonical_location_sql(source['location_expr'])
    rows = db.execute(text(f"""
        SELECT DISTINCT {location} AS name
        FROM {source['source_table']}
        WHERE 1=1 {source['snapshot_filter']}
    """)).fetchall()
    return {row.name: _public_territory_name(row.name) for row in rows if row.name}


def _public_territory_sql(source: dict, catalog: Dict[str, str]) -> str:
    """Expresión SQL que traduce cada lugar crudo a su nombre ciudadano unificado."""
    location = _canonical_location_sql(source['location_expr'])
    branches = " ".join(
        f"WHEN {_sql_literal(raw)} THEN {_sql_literal(display)}"
        for raw, display in sorted(catalog.items()) if raw != display
    )
    return f"(CASE {location} {branches} ELSE {location} END)" if branches else location


def _public_filter_clause(source: dict, conducta: Optional[str], zona: Optional[str], territorio: Optional[str],
                          territory_sql: Optional[str] = None, territory_catalog: Optional[Dict[str, str]] = None):
    clauses = []
    params = {}
    canonical_expr = _canonical_conducta_sql(source['conducta_col'])
    if conducta:
        normalized = conducta.strip().upper().replace(' ', '_')
        matching_code = next(
            (
                code for code, label in CONDUCTA_PUBLIC_LABELS.items()
                if normalized in {code, label.upper().replace(' ', '_')}
            ),
            normalized,
        )
        clauses.append(f"AND {canonical_expr} = :conducta")
        params['conducta'] = matching_code
    if zona:
        clauses.append(f"AND UPPER({source['zone_expr']}) = :zona")
        params['zona'] = zona.strip().upper()
    if territorio:
        requested = territorio.strip()
        if territory_sql and territory_catalog is not None:
            # Acepta el nombre ciudadano ("Potrerito") y, por enlaces antiguos, el nombre crudo.
            display = territory_catalog.get(requested.upper(), requested)
            by_upper = {name.upper(): name for name in set(territory_catalog.values())}
            display = by_upper.get(display.upper(), display)
            clauses.append(f"AND {territory_sql} = :territorio")
            params['territorio'] = display
        else:
            clauses.append(f"AND {_canonical_location_sql(source['location_expr'])} = :territorio")
            params['territorio'] = requested.upper()
    return '\n'.join(clauses), params


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



# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────


@router.get("/public/dashboard")
def get_public_dashboard(
    response: Response,
    year: Optional[int] = None,
    period_mode: str = Query('year_to_date'),
    comparison: str = Query('same_period_previous_year'),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    conducta: Optional[str] = None,
    zona: Optional[str] = None,
    territorio: Optional[str] = None,
    include_map: bool = Query(True),
    min_location_count: int = Query(PUBLIC_MAP_MIN_LOCATION_COUNT, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Dashboard ciudadano: solo datos agregados, anonimizados y trazables."""
    if comparison not in {'same_period_previous_year', 'previous_period', 'none'}:
        raise HTTPException(status_code=400, detail='Comparacion no soportada.')

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
    period_start, period_end, target_year = _resolve_public_period(max_date, year, period_mode, start_date, end_date)
    period_end = min(period_end, max_date)
    if period_start > period_end:
        raise HTTPException(status_code=400, detail='El periodo solicitado es posterior al corte disponible.')
    previous_start, previous_end = _comparison_period(period_start, period_end, comparison)
    territory_catalog = _public_territory_catalog(db, source)
    territory_sql = _public_territory_sql(source, territory_catalog)
    filter_sql, filter_params = _public_filter_clause(
        source, conducta, zona, territorio, territory_sql=territory_sql, territory_catalog=territory_catalog
    )

    base_params = {"start": period_start, "end": period_end, **filter_params}
    if source["snapshot_id"]:
        base_params["snapshot_id"] = source["snapshot_id"]

    total_actual = _public_count(db, source, period_start, period_end, filter_sql, filter_params)
    total_prev = (
        _public_count(db, source, previous_start, previous_end, filter_sql, filter_params)
        if previous_start and previous_end else 0
    )

    volume_row = db.execute(text(f"""
        SELECT COUNT(*) AS registros
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
    """), base_params).first()

    canonical_expr = _canonical_conducta_sql(source['conducta_col'])
    # Los territorios se agrupan por su nombre ciudadano unificado (ver _public_territory_name).
    canonical_location_expr = territory_sql
    hom_stmt = text(f"""
        SELECT COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        AND {canonical_expr} = 'HOMICIDIO'
        {source['snapshot_filter']}
        {filter_sql}
    """)
    homicidios = db.execute(hom_stmt, base_params).first().total or 0
    population = _jamundi_population(period_end)
    # La población es municipal: con filtro de territorio o zona la tasa no sería válida.
    tasa_homicidios = None if (territorio or zona) else rate_per_100k(homicidios, population)

    monthly = db.execute(text(f"""
        SELECT TO_CHAR(date_trunc('month', {source['date_col']}), 'YYYY-MM') AS bucket,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1, date_trunc('month', {source['date_col']})
        ORDER BY date_trunc('month', {source['date_col']})
    """), base_params).fetchall()

    weekly = db.execute(text(f"""
        SELECT EXTRACT(YEAR FROM {source['date_col']})::int AS anio,
               EXTRACT(WEEK FROM {source['date_col']})::int AS semana,
               MIN(date_trunc('week', {source['date_col']}))::date AS week_start,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1, 2
        ORDER BY 1, 2
    """), base_params).fetchall()

    # Día de la semana (1 = lunes). La fecha del hecho es confiable; la hora no se publica.
    weekday_rows = db.execute(text(f"""
        SELECT EXTRACT(ISODOW FROM {source['date_col']})::int AS dia,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1
    """), base_params).fetchall()
    weekday_totals = {row.dia: int(row.total) for row in weekday_rows}

    current_conductas = db.execute(text(f"""
        SELECT {canonical_expr} AS code,
               COUNT(DISTINCT {source['identity_expr']}) AS value
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1
        ORDER BY value DESC, code ASC
        LIMIT 12
    """), base_params).fetchall()

    previous_conductas = []
    comparison_monthly = []
    if previous_start and previous_end:
        previous_params = {"start": previous_start, "end": previous_end, **filter_params}
        if source["snapshot_id"]:
            previous_params["snapshot_id"] = source["snapshot_id"]
        previous_conductas = db.execute(text(f"""
            SELECT {canonical_expr} AS code,
                   COUNT(DISTINCT {source['identity_expr']}) AS value
            FROM {source['source_table']}
            WHERE {source['date_col']} BETWEEN :start AND :end
            {source['snapshot_filter']}
            {filter_sql}
            GROUP BY 1
        """), previous_params).fetchall()
        comparison_monthly = db.execute(text(f"""
            SELECT TO_CHAR(date_trunc('month', {source['date_col']}), 'YYYY-MM') AS bucket,
                   COUNT(DISTINCT {source['identity_expr']}) AS total
            FROM {source['source_table']}
            WHERE {source['date_col']} BETWEEN :start AND :end
            {source['snapshot_filter']}
            {filter_sql}
            GROUP BY 1, date_trunc('month', {source['date_col']})
            ORDER BY date_trunc('month', {source['date_col']})
        """), previous_params).fetchall()

    previous_by_conducta = {row.code: row.value for row in previous_conductas}
    conductas = []
    for row in current_conductas:
        previous_value = previous_by_conducta.get(row.code, 0)
        conductas.append({
            "code": row.code,
            "name": _public_conducta_label(row.code),
            "value": row.value,
            "previous_value": previous_value,
            "difference": row.value - previous_value,
            "variation_pct": _pct_change(row.value, previous_value) if previous_start else None,
        })

    zones = db.execute(text(f"""
        SELECT UPPER({source['zone_expr']}) AS zona,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1
        ORDER BY total DESC
    """), base_params).fetchall()

    raw_locations = db.execute(text(f"""
        SELECT {canonical_location_expr} AS name,
               COUNT(DISTINCT {source['identity_expr']}) AS total,
               STRING_AGG(DISTINCT UPPER(COALESCE({source['zone_expr']}, 'SIN DATO')), '|') AS zones,
               STRING_AGG(DISTINCT {canonical_expr}, '|') AS conductas
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        {filter_sql}
        GROUP BY 1
        ORDER BY total DESC, name ASC
        LIMIT 120
    """), base_params).fetchall()

    previous_locations = {}
    if previous_start and previous_end:
        previous_location_rows = db.execute(text(f"""
            SELECT {canonical_location_expr} AS name,
                   COUNT(DISTINCT {source['identity_expr']}) AS total
            FROM {source['source_table']}
            WHERE {source['date_col']} BETWEEN :start AND :end
            {source['snapshot_filter']}
            {filter_sql}
            GROUP BY 1
        """), previous_params).fetchall()
        previous_locations = {row.name: row.total for row in previous_location_rows}

    catalog_params = {"start": period_start, "end": period_end}
    if source["snapshot_id"]:
        catalog_params["snapshot_id"] = source["snapshot_id"]
    catalog_conductas = db.execute(text(f"""
        SELECT {canonical_expr} AS code,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY total DESC, code ASC
    """), catalog_params).fetchall()
    catalog_zones = db.execute(text(f"""
        SELECT UPPER({source['zone_expr']}) AS name,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY total DESC, name ASC
    """), catalog_params).fetchall()
    catalog_locations = db.execute(text(f"""
        SELECT {canonical_location_expr} AS name,
               COUNT(DISTINCT {source['identity_expr']}) AS total
        FROM {source['source_table']}
        WHERE {source['date_col']} BETWEEN :start AND :end
        {source['snapshot_filter']}
        GROUP BY 1
        ORDER BY total DESC, name ASC
        LIMIT 300
    """), catalog_params).fetchall()
    available_year_rows = db.execute(text(f"""
        SELECT DISTINCT EXTRACT(YEAR FROM {source['date_col']})::int AS year
        FROM {source['source_table']}
        WHERE {source['date_col']} IS NOT NULL
        {source['snapshot_filter']}
        ORDER BY year DESC
    """), params).fetchall()

    from services.geocoding_service import GeocodingService
    suppressed_locations = 0
    excluded_non_territorial_count = 0
    territories = []
    map_points_by_territory = {}
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
        if not _is_publishable_location(row.name):
            excluded_non_territorial_count += row.total or 0
            continue
        if row.total < min_location_count:
            suppressed_locations += row.total
            unmapped_locations_list.append({"name": row.name, "total": row.total, "reason": "baja frecuencia"})
            continue
        previous_value = previous_locations.get(row.name, 0)
        item = {
            "name": row.name,
            "total": row.total,
            "previous_value": previous_value,
            "difference": row.total - previous_value,
            "variation_pct": _pct_change(row.total, previous_value) if previous_start else None,
            "zones": split_values(row.zones),
            "conductas": [_public_conducta_label(code) for code in split_values(row.conductas)],
        }
        territories.append(item)
        territory = None
        if include_map:
            raw_names = [raw for raw, display in territory_catalog.items() if display == row.name] or [row.name]
            territory = next(
                (found for found in (GeocodingService.get_official_territory(raw) for raw in raw_names) if found), None
            )
        if territory:
            # Varias denominaciones de la sabana (p. ej. "CGTO POTRERITO" y "POTRERITO (24-S-02)")
            # resuelven al mismo poligono: se agregan en un solo territorio para no apilar capas.
            territory_key = territory.get("name") or row.name
            existing = map_points_by_territory.get(territory_key)
            if existing:
                existing["total"] += row.total
                existing["aliases"].append(row.name)
                existing["zones"] = sorted(set(existing["zones"]) | set(item["zones"]))
                existing["conductas"] = sorted(set(existing["conductas"]) | set(item["conductas"]))
                continue
            lat, lng = territory["coords"]
            map_points_by_territory[territory_key] = {
                "name": territory_key,
                "total": row.total,
                "aliases": [row.name],
                "lat": lat,
                "lng": lng,
                "geometry": territory["geometry"],
                "source": territory.get("source", "cartografia oficial"),
                "zones": item["zones"],
                "conductas": item["conductas"],
            }
        elif include_map:
            unmapped_locations += 1
            unmapped_locations_list.append({"name": row.name, "total": row.total, "reason": pending_reason(row.name), "zones": item["zones"], "conductas": item["conductas"]})

    map_points = sorted(map_points_by_territory.values(), key=lambda point: point["total"], reverse=True)

    run = source["run"]
    report_start = period_start.isoformat()
    report_end = period_end.isoformat()
    bulletin_url = f"/api/reportes/generar-boletin?fuente=POLICIA_SEMANAL&fecha_inicio={report_start}&fecha_fin={report_end}"
    comparison_label = {
        'same_period_previous_year': 'Mismo periodo del año anterior',
        'previous_period': 'Periodo inmediatamente anterior',
        'none': 'Sin comparación',
    }[comparison]
    available_territories = [
        {"name": row.name, "value": row.total}
        for row in catalog_locations
        if _is_publishable_location(row.name) and row.total >= min_location_count
    ]

    return {
        "metadata": {
            "source": "SÁBANA SIEDCO/PONAL - Policía Nacional",
            "basis": "BASE_MAESTRA_CONSOLIDADA",
            "period_start": report_start,
            "period_end": report_end,
            "latest_event_date": max_date.isoformat(),
            "first_available_date": min_date.isoformat(),
            "year": target_year,
            "scope": period_mode.upper(),
            "comparison_mode": comparison,
            "comparison_label": comparison_label,
            "comparison_start": previous_start.isoformat() if previous_start else None,
            "comparison_end": previous_end.isoformat() if previous_end else None,
            "population": population,
            "population_source": "DANE - Proyecciones municipales CNPV 2018",
            "population_year": period_end.year,
            "privacy": "Publicación agregada. No incluye nombres, identificadores, teléfonos, descripciones individuales, direcciones exactas ni coordenadas puntuales.",
            "methodology": "Cada sábana oficial se valida y se conserva como evidencia. La publicación ciudadana usa una base maestra consolidada: las entregas más recientes actualizan hechos ya existentes y las entregas históricas completan hechos distintos. El mapa solo ubica territorios con polígono oficial verificado, mediante un punto interior de ese polígono; los demás se conservan en las tablas sin ubicación cartográfica.",
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
            "variation_pct": _pct_change(total_actual, total_prev) if previous_start else None,
        },
        "interannual": {
            "current": {"year": period_end.year, "total": total_actual, "start": period_start.isoformat(), "end": period_end.isoformat()},
            "previous": {"year": previous_end.year if previous_end else None, "total": total_prev, "start": previous_start.isoformat() if previous_start else None, "end": previous_end.isoformat() if previous_end else None},
            "variation_pct": _pct_change(total_actual, total_prev) if previous_start else None,
        },
        "monthly_trend": [{"name": row.bucket, "total": row.total} for row in monthly],
        "comparison_monthly_trend": [{"name": row.bucket, "total": row.total} for row in comparison_monthly],
        # complete: la semana (lunes a domingo) termina dentro del periodo consultado.
        # preliminary: cae en los últimos días de la entrega policial, que se completan con reportes tardíos.
        "weekday": [{"day": day, "total": weekday_totals.get(day, 0)} for day in range(1, 8)],
        "weekly_trend": [
            {
                "name": f"S{row.semana:02d}", "year": row.anio, "semana": row.semana, "total": row.total,
                "start": row.week_start.isoformat() if row.week_start else None,
                "end": (row.week_start + timedelta(days=6)).isoformat() if row.week_start else None,
                "complete": bool(row.week_start and row.week_start + timedelta(days=6) <= period_end),
                "preliminary": bool(row.week_start and row.week_start + timedelta(days=6) > max_date - timedelta(days=7)),
            }
            for row in weekly
        ],
        "conductas": conductas,
        "priority_kpis": conductas[:4],
        "zones": [{"name": row.zona or "SIN DATO", "value": row.total} for row in zones],
        "territories": territories[:20],
        "filters": {
            "selected": {
                "year": year,
                "period_mode": period_mode,
                "comparison": comparison,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "conducta": conducta,
                "zona": zona,
                "territorio": territorio,
                "include_map": include_map,
            },
            "available": {
                "years": [row.year for row in available_year_rows],
                "conductas": [{"code": row.code, "name": _public_conducta_label(row.code), "value": row.total} for row in catalog_conductas],
                "zones": [{"name": row.name or "SIN DATO", "value": row.total} for row in catalog_zones],
                "territories": available_territories,
            },
        },
        "map": {
            "type": "official_territory_polygons",
            "min_location_count": min_location_count,
            "suppressed_count": suppressed_locations,
            "excluded_non_territorial_count": excluded_non_territorial_count,
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
    """KPIs del dashboard — fuente: hechos_seguridad (sabanas SIEDCO)."""
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

        population = _jamundi_population(end_date)
        tasa_homicidios = rate_per_100k(homicidios, population)

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
            "poblacion":         population,
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
    """Tendencia por día, semana o mes desde la sábana policial consolidada."""
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
    hurto_vals = tuple({
        value
        for key in ('HURTO_PERSONAS', 'HURTO_VEHICULOS', 'HURTO_COMERCIO', 'HURTO_RESIDENCIAS')
        for value in CONDUCTA_KEYS[key]
    })
    vif_vals = tuple(CONDUCTA_KEYS['VIF'])
    lesiones_vals = tuple(CONDUCTA_KEYS['LESIONES'])

    snapshot_id = None
    source_table = "hechos_seguridad"
    identity_expr = "COALESCE(NULLIF(BTRIM(id_fuente), ''), NULLIF(BTRIM(fingerprint), ''), id::text)"

    query_str = f"""
        SELECT
            date_trunc('{intervalo}', fecha_evento) as full_date,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar IN :hom_vals) as homicidios,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar IN :hurto_vals) as hurtos,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar IN :vif_vals) as vif,
            COUNT(DISTINCT {identity_expr}) FILTER (WHERE conducta_estandar IN :lesiones_vals) as lesiones
        FROM {source_table}
        WHERE 1=1
        AND fuente_codigo = 'POLICIA_SEMANAL'
    """
    params = {
        "hom_vals": homicidio_vals,
        "hurto_vals": hurto_vals,
        "vif_vals": vif_vals,
        "lesiones_vals": lesiones_vals,
    }

    if snapshot_id:
        query_str += " AND ingestion_id = :snapshot_id"
        params["snapshot_id"] = snapshot_id

    if start_date:
        query_str += " AND fecha_evento >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query_str += " AND fecha_evento <= :end_date"
        params["end_date"] = end_date

    query_str += " GROUP BY 1 ORDER BY 1 DESC"

    if not start_date:
        query_str += " LIMIT 12"

    statement = text(query_str).bindparams(
        bindparam("hom_vals", expanding=True),
        bindparam("hurto_vals", expanding=True),
        bindparam("vif_vals", expanding=True),
        bindparam("lesiones_vals", expanding=True),
    )
    results = db.execute(statement, params).fetchall()

    def translate_label(label):
        for en, es in MESES_ES.items():
            label = label.replace(en, es)
        return label

    def format_label(value):
        if intervalo == "day":
            label = value.strftime("%d %b")
        elif intervalo == "week":
            label = f"Sem {value.strftime('%d %b')}"
        else:
            label = value.strftime("%b %Y")
        return translate_label(label)

    trend_data = [
        {
            "name": format_label(r.full_date),
            "homicidios": r.homicidios,
            "hurtos": r.hurtos,
            "vif": r.vif,
            "lesiones": r.lesiones,
        }
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


@router.get("/estadisticas/resumen", dependencies=[Depends(institutional_access)])
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
            desc_parts.append(f"(Víctima: {h.sexo}, {h.edad} años)")

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
    population = _jamundi_population(end_date)
    tasa = rate_per_100k(conteo, population)

    return {
        "categoria":          "HOMICIDIO",
        "total_eventos":      conteo,
        "tasa_por_100k":      tasa,
        "periodo": {
            "inicio": start_date if start_date else "Histórico",
            "fin":    end_date if end_date else "Actual"
        },
        "poblacion_referencia": population
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
    """Hechos agrupados por semana del año para análisis temporal."""
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
    """Distribución de hechos por zona (urbana/rural/corregimiento)."""
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


# ─────────────────────────────────────────────
# DATOS ABIERTOS VERSIONADOS (CC BY 4.0)
# Reusa el tablero ciudadano sin duplicar su lógica: el payload del
# dashboard se transforma en un paquete citable con hash de versión.
# ─────────────────────────────────────────────

OPEN_DATA_LICENSE = {
    "name": "Creative Commons Atribución 4.0 Internacional",
    "short": "CC BY 4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/deed.es",
}

OPEN_DATA_DICTIONARY = [
    {"field": "dataset", "description": "Grupo de información publicado."},
    {"field": "category", "description": "Nombre ciudadano del indicador, conducta, zona o territorio."},
    {"field": "current_value", "description": "Valor agregado del periodo seleccionado."},
    {"field": "comparison_value", "description": "Valor agregado del periodo usado como comparación."},
    {"field": "period_start", "description": "Fecha inicial del periodo consultado, formato AAAA-MM-DD."},
    {"field": "period_end", "description": "Fecha final del periodo consultado, formato AAAA-MM-DD."},
    {"field": "cutoff_date", "description": "Fecha del último registro disponible en la fuente."},
    {"field": "source", "description": "Fuente institucional de la información."},
]

OPEN_DATA_CSV_HEADERS = [
    "dataset", "category", "current_value", "comparison_value",
    "period_start", "period_end", "cutoff_date", "source",
]


def _open_data_value(value):
    return "" if value is None else value


def build_open_data_records(payload):
    """Filas agregadas del paquete, con el mismo esquema de las descargas ciudadanas."""
    payload = payload or {}
    meta = payload.get("metadata") or {}
    kpis = payload.get("kpis") or {}
    rows = []

    def push(dataset, category, current, comparison=""):
        rows.append({
            "dataset": dataset,
            "category": category,
            "current_value": _open_data_value(current),
            "comparison_value": _open_data_value(comparison),
            "period_start": meta.get("period_start") or "",
            "period_end": meta.get("period_end") or "",
            "cutoff_date": meta.get("latest_event_date") or "",
            "source": meta.get("source") or "",
        })

    push("indicadores", "Casos agregados", kpis.get("total_hechos"), kpis.get("previous_total"))
    push("indicadores", "Homicidios", kpis.get("homicidios"))
    for item in payload.get("conductas") or []:
        push("conductas", item.get("name"), item.get("value"), item.get("previous_value", ""))
    for item in payload.get("zones") or []:
        push("zonas", item.get("name"), item.get("value"), item.get("previous_value", ""))
    for item in payload.get("territories") or []:
        push("territorios", item.get("name"), item.get("total"), item.get("previous_value", ""))
    return rows


def open_data_version(records, metadata, filters):
    """Hash SHA-256 del contenido canónico: identifica la versión del dataset."""
    canonical = json.dumps(
        {"metadata": metadata, "filters": filters, "records": records},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_open_data_package(payload):
    """Paquete citable: metadatos + licencia + versión + diccionario + registros.

    La versión es un hash del contenido (sin generated_at): los mismos datos
    y filtros siempre producen la misma versión, en cualquier momento.
    """
    payload = payload or {}
    meta = payload.get("metadata") or {}
    records = build_open_data_records(payload)
    filters = (payload.get("filters") or {}).get("selected") or {}
    metadata = {
        "title": "SISC Jamundí — Datos públicos agregados de seguridad y convivencia",
        "publisher": "Alcaldía de Jamundí — Secretaría de Seguridad y Convivencia",
        "cutoff_date": meta.get("latest_event_date") or "",
        "period_start": meta.get("period_start") or "",
        "period_end": meta.get("period_end") or "",
        "comparison": meta.get("comparison_label") or "",
        "source": meta.get("source") or "",
        "privacy": meta.get("privacy") or "",
        "methodology": meta.get("methodology") or "",
        "license": OPEN_DATA_LICENSE,
    }
    metadata["version"] = open_data_version(records, metadata, filters)
    metadata["generated_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "metadata": metadata,
        "filters": filters,
        "data_dictionary": OPEN_DATA_DICTIONARY,
        "records": records,
    }


def open_data_csv_text(package):
    """Render CSV del paquete (solo registros; los metadatos viajan en el JSON)."""
    package = package or {}
    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM: Excel en Windows abre el UTF-8 sin romper tildes
    writer = csv.DictWriter(buffer, fieldnames=OPEN_DATA_CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for row in package.get("records") or []:
        writer.writerow({key: ("" if row.get(key) is None else row.get(key)) for key in OPEN_DATA_CSV_HEADERS})
    return buffer.getvalue()


def open_data_filename(package, extension):
    """Nombre estable y citable: incluye corte y hash corto de versión."""
    metadata = (package or {}).get("metadata") or {}
    cutoff = metadata.get("cutoff_date") or "sin-corte"
    digest = (metadata.get("version") or "00000000")[:8]
    return f"sisc-jamundi-datos-abiertos-{cutoff}-{digest}.{extension}"


@router.get("/public/open-data")
def get_public_open_data(
    response: Response,
    format: str = Query("json", pattern="^(json|csv)$"),
    year: Optional[int] = None,
    period_mode: str = Query("year_to_date"),
    comparison: str = Query("same_period_previous_year"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    conducta: Optional[str] = None,
    zona: Optional[str] = None,
    territorio: Optional[str] = None,
    min_location_count: int = Query(PUBLIC_MAP_MIN_LOCATION_COUNT, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Dataset ciudadano versionado (CC BY 4.0), derivado del tablero público."""
    payload = get_public_dashboard(
        Response(),
        year=year,
        period_mode=period_mode,
        comparison=comparison,
        start_date=start_date,
        end_date=end_date,
        conducta=conducta,
        zona=zona,
        territorio=territorio,
        include_map=False,
        min_location_count=min_location_count,
        db=db,
    )
    package = build_open_data_package(payload)
    metadata = package["metadata"]
    if format == "csv":
        filename = open_data_filename(package, "csv")
        return Response(
            content=open_data_csv_text(package),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Dataset-Hash": metadata["version"],
                "X-Dataset-Cutoff": metadata["cutoff_date"],
                "X-Dataset-License": OPEN_DATA_LICENSE["short"],
            },
        )
    return package








