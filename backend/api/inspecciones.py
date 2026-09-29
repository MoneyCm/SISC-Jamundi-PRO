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
    # Usar query cruda para extraer lat/lng de PostGIS
    sql = text("""
        SELECT id, numero_expediente, departamento, municipio, localidad, 
               ST_X(geom_punto) as lng, ST_Y(geom_punto) as lat 
        FROM inspeccion_expedientes
        WHERE (:localidad IS NULL OR localidad ILIKE :localidad_pattern)
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :skip
    """)
    
    params = {
        "localidad": localidad, 
        "localidad_pattern": f"%{localidad}%" if (localidad and localidad.strip()) else "%%",
        "limit": limit,
        "skip": skip
    }
    
    results = db.execute(sql, params).fetchall()
    items = [dict(r._mapping) for r in results]
    total = db.query(InspeccionExpediente).count()
    
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
    # KPIs rápidos
    total_exp = db.query(InspeccionExpediente).count()
    total_med = db.query(InspeccionMedida).count()
    
    estados = db.query(
        InspeccionMedida.estado_actual, 
        func.count(InspeccionMedida.id)
    ).group_by(InspeccionMedida.estado_actual).all()
    
    return {
        "total_expedientes": total_exp,
        "total_medidas": total_med,
        "por_estado": {e: c for e, c in estados}
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
