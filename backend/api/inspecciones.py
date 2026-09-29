from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.session import get_db
from services.inspeccion_service import InspeccionService
from db.models_inspecciones import InspeccionExpediente, InspeccionMedida, InspeccionActuacion
from sqlalchemy import func, text

from api.auth import institutional_access, require_role
from db.models import User
from db import crud_dq
from services import dq_service

router = APIRouter()
INSPECTIONS_UPLOAD_ROLES = ["ANALYST", "DIRECTIVE", "SOURCE_UPLOADER", "FUNC_ADMIN", "TI_ADMIN"]

@router.post("/upload")
async def upload_inspecciones(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(INSPECTIONS_UPLOAD_ROLES)),
):
    """Carga los reportes del RNMC: medidas gestionadas o comparendos (medidas pendientes)."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use Excel.")
    
    content = await file.read()
    service = InspeccionService(db)
    try:
        # La calidad se revisa sobre el formato RNMC ya convertido (los comparendos traen otras columnas).
        frame, _format = service.read_frame(content)
        quality_report = dq_service.run_frame_dq(
            frame, file.filename or "archivo_sin_nombre", source_name="INSPECCIONES_POLICIA", profile="INSPECCIONES")
    except Exception:
        quality_report = dq_service.run_dq(
            content,
            file.filename or "archivo_sin_nombre",
            source_name="INSPECCIONES_POLICIA",
            profile="INSPECCIONES",
        )
    db_quality_report = crud_dq.create_dq_report(db, quality_report)
    if quality_report.get("semaforo") == "ROJO":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "La carga de Inspecciones fue bloqueada por errores criticos de calidad.",
                "report_id": str(db_quality_report.id),
                "semaforo": "ROJO",
                "issues_count": len(quality_report.get("issues", [])),
            },
        )

    result = await service.ingest_excel(content, file.filename)
    result["quality"] = {
        "report_id": str(db_quality_report.id),
        "semaforo": quality_report.get("semaforo"),
        "score": quality_report.get("score_overall"),
        "issues_count": len(quality_report.get("issues", [])),
    }
    return result

@router.get("/expedientes")
def get_expedientes(
    skip: int = 0,
    limit: int = 100,
    localidad: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    from services.comparendos_rnmc import etiqueta_articulo

    # Los comparendos más recientes primero (fecha del hecho), con su comportamiento y el estado de sus medidas.
    # La búsqueda sirve por barrio o por número de expediente.
    filtro = "(:localidad IS NULL OR e.localidad ILIKE :localidad_pattern OR e.numero_expediente ILIKE :localidad_pattern)"
    sql = text(f"""
        WITH primera AS (
            SELECT m.expediente_id, MIN(a.fecha_actuacion) AS fecha
            FROM inspeccion_medidas m JOIN inspeccion_actuaciones a ON a.medida_id = m.id
            GROUP BY m.expediente_id
        )
        SELECT e.id, e.numero_expediente, e.localidad,
               ST_X(e.geom_punto) AS lng, ST_Y(e.geom_punto) AS lat, primera.fecha,
               (SELECT m.articulo FROM inspeccion_medidas m
                 WHERE m.expediente_id = e.id AND m.articulo IS NOT NULL LIMIT 1) AS articulo,
               (SELECT string_agg(DISTINCT m.estado_actual, ', ') FROM inspeccion_medidas m
                 WHERE m.expediente_id = e.id) AS estados
        FROM inspeccion_expedientes e
        LEFT JOIN primera ON primera.expediente_id = e.id
        WHERE {filtro}
        ORDER BY primera.fecha DESC NULLS LAST, e.numero_expediente DESC
        LIMIT :limit OFFSET :skip
    """)

    params = {
        "localidad": localidad.strip() if (localidad and localidad.strip()) else None,
        "localidad_pattern": f"%{localidad.strip()}%" if (localidad and localidad.strip()) else "%%",
        "limit": limit,
        "skip": skip
    }

    items = []
    for fila in db.execute(sql, params).fetchall():
        item = dict(fila._mapping)
        item["fecha"] = item["fecha"].date().isoformat() if item["fecha"] else None
        item["comportamiento"] = etiqueta_articulo(item["articulo"]) if item["articulo"] else None
        items.append(item)
    total = db.execute(text(f"SELECT COUNT(*) FROM inspeccion_expedientes e WHERE {filtro}"), params).scalar() or 0

    return {"total": total, "items": items}

@router.get("/expedientes/{numero}")
def get_expediente_detail(
    numero: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    exp = db.query(InspeccionExpediente).filter_by(numero_expediente=numero).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    
    # Cargar medidas y sus actuaciones/finanzas
    return {
        "expediente": exp,
        "medidas": [
            {
                "id": m.id,
                "nombre": m.nombre_medida,
                "estado": m.estado_actual,
                "articulo": m.articulo,
                "comportamiento": m.comportamiento,
                "fechas": {"inicio": m.fecha_inicio, "fin": m.fecha_fin},
                "finanzas": m.finanza,
                "actuaciones": m.actuaciones
            } for m in exp.medidas
        ]
    }

@router.get("/geojson")
def get_inspecciones_geojson(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Retorna los expedientes georreferenciados en formato GeoJSON."""
    sql = text("""
        SELECT id, numero_expediente, localidad, 
               ST_X(geom_punto) as lng, ST_Y(geom_punto) as lat 
        FROM inspeccion_expedientes
        WHERE geom_punto IS NOT NULL
    """)
    
    results = db.execute(sql).fetchall()
    features = []
    
    for r in results:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.lng, r.lat]
            },
            "properties": {
                "id": str(r.id),
                "expediente": r.numero_expediente,
                "localidad": r.localidad
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.get("/stats/summary")
def get_inspecciones_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    # Todas las cifras son del mismo año: el del último comparendo cargado (cada comparendo una vez).
    from datetime import date as fecha_tipo
    from services import comparendos_rnmc

    corte = comparendos_rnmc.corte(db, fecha_tipo.today())
    if not corte:
        return {"anio": None, "comparendos": 0, "medidas": 0, "ratificadas": 0, "pagadas": 0, "por_estado": {}}
    sub = comparendos_rnmc.primeras_fechas(db)
    inicio = datetime.combine(fecha_tipo(corte.year, 1, 1), datetime.min.time())
    estados = dict(
        db.query(InspeccionMedida.estado_actual, func.count(InspeccionMedida.id))
        .join(sub, sub.c.expediente_id == InspeccionMedida.expediente_id)
        .filter(sub.c.fecha >= inicio)
        .group_by(InspeccionMedida.estado_actual).all()
    )
    suma = lambda texto: sum(n for estado, n in estados.items() if estado and texto in estado)
    return {
        "anio": corte.year,
        "corte": corte.isoformat(),
        "comparendos": comparendos_rnmc.contar(db, fecha_tipo(corte.year, 1, 1), corte),
        "medidas": sum(estados.values()),
        "ratificadas": suma("RATIFICADA"),
        "pagadas": suma("PAGADO"),
        "por_estado": estados,
    }


@router.get("/stats/convivencia")
def get_convivencia(
    anio: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Comparendos del año por comportamiento, barrio, día y mes (cada comparendo una vez)."""
    from datetime import date
    from services import comparendos_rnmc

    ultimo = comparendos_rnmc.corte(db, date.today())
    if not ultimo:
        return {"total": 0, "comportamientos": [], "barrios": [], "dias": [], "meses": [], "corte": None}
    anio = anio or ultimo.year
    hasta = min(date(anio, 12, 31), ultimo)
    return comparendos_rnmc.resumen_convivencia(db, date(anio, 1, 1), hasta)


@router.get("/estado-carga")
def get_estado_carga(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Si los reportes del RNMC están al día (aviso en Inicio y en el Centro de fuentes)."""
    from services import comparendos_rnmc

    return comparendos_rnmc.estado_carga(db)


@router.get("/mapa")
def get_mapa_comparendos(
    periodo: str = "year_to_date",
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    articulo: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Capa de comparendos del RNMC para el Mapa territorial (agregada por territorio oficial)."""
    from datetime import date, timedelta
    from services import comparendos_rnmc

    ultimo = comparendos_rnmc.corte(db, date.today())
    if not ultimo:
        return {"metadata": {"available": False}, "map": {"points": []}, "comportamientos": []}
    fin = ultimo
    if periodo == "last_7_days":
        inicio = ultimo - timedelta(days=6)
    elif periodo == "last_30_days":
        inicio = ultimo - timedelta(days=29)
    elif periodo == "custom" and desde and hasta:
        inicio, fin = date.fromisoformat(desde), min(date.fromisoformat(hasta), ultimo)
    else:
        inicio = date(ultimo.year, 1, 1)
    return {
        "metadata": {
            "available": True,
            "source": "RNMC - Policía Nacional (comparendos, cada uno una vez)",
            "period_start": inicio.isoformat(),
            "period_end": fin.isoformat(),
            "latest_event_date": ultimo.isoformat(),
        },
        "map": comparendos_rnmc.capa_mapa(db, inicio, fin, articulo),
        "comportamientos": [{"code": numero, "name": etiqueta, "value": total}
                            for numero, etiqueta, _texto, total in comparendos_rnmc.por_comportamiento(db, inicio, fin, limite=20)],
    }


@router.get("/stats/tendencia")
def get_tendencia(
    db: Session = Depends(get_db),
    current_user: User = Depends(institutional_access),
):
    """Comparendos por año desde 2018: año completo y mismo tramo del año, por comportamiento y por barrio."""
    from services import comparendos_rnmc

    return comparendos_rnmc.tendencia(db)
