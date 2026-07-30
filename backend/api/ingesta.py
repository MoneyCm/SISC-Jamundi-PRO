from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from db.models import get_db, Event, EventType, User
import pandas as pd
import io
import uuid
import hashlib
from typing import List, Dict, Optional, Any
import logging
import traceback
from datetime import datetime

logger = logging.getLogger("sisc_api")

from api.auth import admin_only, analyst_or_admin, ingestion_operator

router = APIRouter()

@router.post("/upload", dependencies=[Depends(analyst_or_admin)])
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Recibe un archivo Excel/CSV, procesa los datos y los inserta en PostGIS.
    Reporta éxitos y fallos individuales por fila.
    """
    contents = await file.read()
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Formato de archivo no soportado")

        # Normalizar nombres de columnas a minúsculas
        df.columns = [c.lower().strip() for c in df.columns]

        required_cols = ['fecha', 'hora', 'delito', 'latitud', 'longitud']
        if not all(col in df.columns for col in required_cols):
            raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {required_cols}")

        report = {
            "total": len(df),
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }

        for index, row in df.iterrows():
            row_num = index + 2 # +1 for 0-index, +1 for header row
            try:
                # 1. Validar y normalizar Categoría
                delito_nombre = str(row.get('delito', '')).upper().strip()
                if not delito_nombre:
                    raise ValueError("El campo 'delito' no puede estar vacío")

                event_type = db.query(EventType).filter(EventType.category == delito_nombre).first()
                if not event_type:
                    event_type = EventType(category=delito_nombre, is_delicto=True)
                    db.add(event_type)
                    db.flush()

                # 2. Parsing de Fecha y Hora con validación
                try:
                    occ_date = pd.to_datetime(row['fecha']).date()
                    occ_time = pd.to_datetime(row['hora']).time()
                except Exception:
                    raise ValueError(f"Formato de fecha/hora inválido (Fecha: {row['fecha']}, Hora: {row['hora']})")

                # 3. Datos de Geometría
                try:
                    lng = float(row['longitud'])
                    lat = float(row['latitud'])
                    if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
                        raise ValueError("Coordenadas fuera de rango válido")
                except (ValueError, TypeError):
                    raise ValueError(f"Coordenadas inválidas (Lat: {row.get('latitud')}, Lng: {row.get('longitud')})")

                # 4. Crear el evento
                new_event = Event(
                    external_id=str(row.get('id_externo', uuid.uuid4())),
                    event_type_id=event_type.id,
                    occurrence_date=occ_date,
                    occurrence_time=occ_time,
                    barrio=str(row.get('barrio', 'Sin especificar')),
                    descripcion=str(row.get('descripcion', '')),
                    estado=str(row.get('estado', 'Abierto'))
                )
                db.add(new_event)
                db.flush()

                # 5. Insertar geometría PostGIS
                db.execute(
                    text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                    {"lng": lng, "lat": lat, "id": new_event.id}
                )
                
                report["success_count"] += 1

            except Exception as row_err:
                report["error_count"] += 1
                report["errors"].append({"fila": row_num, "error": str(row_err)})

        db.commit()
        return {
            "status": "success" if report["error_count"] == 0 else "partial_success",
            "message": f"Carga completada: {report['success_count']} éxitos, {report['error_count']} errores.",
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fatal procesando el archivo: {str(e)}")

@router.post("/bulk", dependencies=[Depends(analyst_or_admin)])
async def bulk_upload(data: List[dict], db: Session = Depends(get_db)):
    """
    Recibe una lista de eventos pre-analizados por la IA en JSON y los inserta.
    """
    report = {
        "total": len(data),
        "success_count": 0,
        "skipped_count": 0,
        "error_count": 0,
        "errors": []
    }

    for index, item in enumerate(data):
        try:
            with db.begin_nested(): # SAVEPOINT: falla solo esta fila si algo sale mal
                # 1. Validar Categoría
                raw_delito = str(item.get('tipo', '')).upper().strip()
                # Normalización inteligente
                delito_nombre = raw_delito
                if 'H.PERSONA' in raw_delito or raw_delito == 'H. PERSONAS': delito_nombre = 'HURTO A PERSONAS'
                elif 'H.COMERCIO' in raw_delito: delito_nombre = 'HURTO A COMERCIO'
                elif 'H.RESIDENCIA' in raw_delito: delito_nombre = 'HURTO A RESIDENCIAS'
                elif 'H.MOTOS' in raw_delito: delito_nombre = 'HURTO A MOTOCICLETAS'
                elif 'H.AUTOMO' in raw_delito: delito_nombre = 'HURTO A AUTOMOTORES'
                elif 'L.PERSONALES' in raw_delito or 'LESIONES' in raw_delito: delito_nombre = 'LESIONES PERSONALES'
                elif 'HOMICI' in raw_delito: delito_nombre = 'HOMICIDIO'
                elif 'VIOLENCIA' in raw_delito or 'VIF' in raw_delito: delito_nombre = 'VIOLENCIA INTRAFAMILIAR'

                event_type = db.query(EventType).filter(EventType.category == delito_nombre).first()
                if not event_type:
                    event_type = EventType(category=delito_nombre, is_delicto=True)
                    db.add(event_type)
                    db.flush()

                # 2. Fecha y Hora
                def parse_robust_time(val):
                    if not val or str(val).lower() == 'undefined' or str(val).strip() == '':
                        return datetime.strptime("00:00", "%H:%M").time()
                    val_str = str(val).split('-')[0].strip()
                    try:
                        if ':' in val_str:
                            parts = val_str.split(':')
                            h = int(parts[0])
                            m = int(parts[1]) if len(parts) > 1 else 0
                            return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
                        return pd.to_datetime(val_str).time()
                    except:
                        return datetime.strptime("00:00", "%H:%M").time()

                def parse_robust_date(val):
                    if not val or str(val).lower() == 'undefined':
                        return datetime.now().date()
                    try:
                        return pd.to_datetime(val).date()
                    except:
                        try:
                            val_clean = str(val).split(' ')[0]
                            return pd.to_datetime(val_clean).date()
                        except:
                            return datetime.now().date()

                occ_date = parse_robust_date(item.get('fecha'))
                occ_time = parse_robust_time(item.get('hora'))
                barrio = str(item.get('barrio', 'Sin especificar'))

                # 2.5 DETECCIÓN DE DUPLICADOS (Opción B elegida por el usuario)
                existing_event = db.query(Event).filter(
                    Event.occurrence_date == occ_date,
                    Event.occurrence_time == occ_time,
                    Event.event_type_id == event_type.id,
                    Event.barrio == barrio
                ).first()

                if existing_event:
                    report["skipped_count"] += 1
                    continue

                # 3. Geometría
                try:
                    def clean_coord(c):
                        if not c or str(c).lower() == 'undefined': return None
                        return float(str(c).replace(',', '.'))
                    lat = clean_coord(item.get('latitud')) or 3.26
                    lng = clean_coord(item.get('longitud')) or -76.53
                except:
                    lat, lng = 3.26, -76.53

                # 4. Crear Evento
                new_event = Event(
                    external_id=str(item.get('id_externo', uuid.uuid4())),
                    event_type_id=event_type.id,
                    occurrence_date=occ_date,
                    occurrence_time=occ_time,
                    barrio=barrio,
                    descripcion=str(item.get('descripcion', '')),
                    estado=str(item.get('estado', 'Abierto'))
                )
                db.add(new_event)
                db.flush()

                # 5. PostGIS
                db.execute(
                    text("UPDATE events SET location_geom = ST_SetSRID(ST_Point(:lng, :lat), 4326) WHERE id = :id"),
                    {"lng": lng, "lat": lat, "id": new_event.id}
                )
                report["success_count"] += 1
            
            # Commit masivo cada 50 filas (Mucho más rápido)
            if index % 50 == 0:
                db.commit()

        except Exception as e:
            # El uso de begin_nested() hace rollback automático de ESTA fila si falla
            report["error_count"] += 1
            report["errors"].append({"index": index, "error": str(e)})

    db.commit() # Commit final de lo que quede pendiente
    return {
        "status": "success" if report["error_count"] == 0 else "partial_success",
        "message": f"Carga masiva completada: {report['success_count']} nuevos, {report['skipped_count']} duplicados omitidos.",
        "report": report
    }

@router.delete("/clear", dependencies=[Depends(analyst_or_admin)])
def clear_all_events(db: Session = Depends(get_db)):
    """Elimina todos los eventos de la base de datos"""
    db.query(Event).delete()
    db.commit()
    return {"message": "Base de datos de eventos limpiada correctamente"}

@router.delete("/{event_id}", dependencies=[Depends(analyst_or_admin)])
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """Elimina un evento específico"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(event)
    db.commit()
    return {"message": "Evento eliminado correctamente"}



def _process_policia_background(contents: bytes, filename: str, username: str, run_id: str = None, force: bool = False):
    from db.session import SessionLocal
    from services.excel_policia_processor import PoliciaJamundiProcessor

    db = SessionLocal()
    try:
        processor = PoliciaJamundiProcessor(db, user_id=username)
        processor.process(contents, filename, run_id=run_id, force=force)
    except Exception:
        logger.error(f"Fallo en procesador Policia background: {filename}")
        logger.error(traceback.format_exc())
    finally:
        db.close()

# --- GATE DE INGESTA NUEVO ---
from services import dq_service
from db import crud_dq

@router.post("/gate/{dataset_code}")
async def upload_with_gate(
    dataset_code: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(ingestion_operator),
):
    """
    Universal Ingestion Gate:
    1. Verifica status en el catálogo MinDefensa.
    2. Ejecuta DQ (Data Quality).
    3. Persiste reporte DQ.
    4. Bloquea si hay semáforo ROJO (a menos que force=True).
    5. Carga datos si pasa el gate.
    """
    dataset_code = dataset_code.upper()
    contents = await file.read()
    
    # Procesador especializado para Policia Jamundi. En Render se ejecuta en segundo plano
    # para evitar que la conexion HTTP quede leyendo hasta agotar timeout.
    if dataset_code == "POLICIA_SEMANAL":
        from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow

        file_hash = hashlib.sha256(contents).hexdigest()
        existing_run = db.query(IngestionRun).filter(
            IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            IngestionRun.hash_archivo == file_hash,
        ).first()

        if existing_run and not force:
            has_snapshot = db.query(SabanaSnapshotRow.id).filter(
                SabanaSnapshotRow.ingestion_id == existing_run.id
            ).first() is not None
            if has_snapshot and existing_run.status == "COMPLETED":
                return {
                    "status": "skipped",
                    "message": "Este archivo ya fue procesado anteriormente.",
                    "ingestion_id": str(existing_run.id),
                    "report_id": str(existing_run.id),
                }
            run = existing_run
            run.status = "IN_PROGRESS"
            run.usuario_carga = current_user.username
            run.fecha_fin = None
        else:
            run = IngestionRun(
                fuente_codigo="POLICIA_SEMANAL",
                hash_archivo=file_hash,
                filename=file.filename,
                usuario_carga=current_user.username,
                status="IN_PROGRESS",
            )
            db.add(run)

        db.commit()
        db.refresh(run)
        background_tasks.add_task(_process_policia_background, contents, file.filename, current_user.username, str(run.id), force)
        return {
            "status": "accepted",
            "message": "La base policial quedo en procesamiento. Puedes seguir el avance con el ID de proceso.",
            "report_id": str(run.id),
            "ingestion_id": str(run.id),
        }

    # Resto de fuentes (MinDefensa / SIEDCO)
    if dataset_code.startswith("POLICIA_"):
        source_name = "POLICIA_PORTAL"
    else:
        source_name = f"{dataset_code}_SYNC" if "MINDEFENSA" not in dataset_code else dataset_code
    
    # 0. Verificar si el asset de MinDefensa en el catálogo está actualizado
    from db.models_mindefensa import MindefensaAsset
    asset = db.query(MindefensaAsset).filter(MindefensaAsset.dataset_code == dataset_code).first()
    if asset and asset.status == "UPDATED" and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"El dataset de {dataset_code} en MinDefensa fue actualizado. Por favor, descargue la versión más reciente antes de ingestar.",
                "dataset_code": dataset_code,
                "last_change": asset.last_change_detected_at.isoformat() if asset.last_change_detected_at else None
            }
        )

    # 1 y 2. DQ y Persistencia de evidencia
    report_data = dq_service.run_dq(contents, file.filename, source_name)
    db_report = crud_dq.create_dq_report(db, report_data)
    
    # 3. Validar Semáforo — omitir bloqueo si force=True
    if report_data.get("semaforo") == "ROJO" and not force:
        raise HTTPException(
            status_code=422, 
            detail={
                "message": "Archivo rechazado por fallos críticos de calidad.",
                "report_id": str(db_report.id),
                "semaforo": "ROJO",
                "issues_count": len(report_data.get("issues", []))
            }
        )
    
    # 4. Ingesta (Si pasó el gate)
    try:
        from services.file_reader import smart_read_file
        df = smart_read_file(contents)
            
        # El sistema espera ciertas columnas para Event, aquí usamos el mapeo de Mindefensa
        ingestion_id = uuid.uuid4()
        success_count = 0
        
        # Asegurar columnas en mayúsculas para el mapeo
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        for index, row in df.iterrows():
            try:
                # Mapeo flexible
                row_dict = {k.upper(): v for k, v in row.to_dict().items()}
                
                fecha_val = row_dict.get('FECHA_HECHO') or row_dict.get('FECHA')
                if not fecha_val: continue
                
                occ_date = pd.to_datetime(fecha_val).date()
                cond = str(row_dict.get('DESCRIPCION CONDUCTA') or row_dict.get('DELITO') or dataset_code).upper().strip()
                
                # Buscar o crear tipo
                event_type = db.query(EventType).filter(EventType.category == cond).first()
                if not event_type:
                    event_type = EventType(category=cond, is_delicto=True)
                    db.add(event_type)
                    db.flush()

                # Intentar leer hora
                hora_str = str(row_dict.get('HORA_HECHO') or row_dict.get('HORA24') or row_dict.get('HORA') or "00:00").split(' ')[0]
                try:
                    occ_time = datetime.strptime(hora_str, "%H:%M").time()
                except:
                    try:
                        occ_time = pd.to_datetime(hora_str).time()
                    except:
                        occ_time = datetime.strptime("00:00", "%H:%M").time()

                new_event = Event(
                    external_id=str(row_dict.get('HECHOS_ID') or uuid.uuid4()),
                    event_type_id=event_type.id,
                    occurrence_date=occ_date,
                    occurrence_time=occ_time,
                    barrio=str(row_dict.get('BARRIOS_HECHO') or row_dict.get('BARRIOS HECHO') or row_dict.get('MUNICIPIO') or row_dict.get('BARRIO') or 'Jamundí'),
                    descripcion=str(row_dict.get('CLASE_SITIO') or row_dict.get('MODALIDAD') or row_dict.get('ARMAS_MEDIOS') or f"Ingesta DQ: {source_name}"),

                    # Trazabilidad
                    dq_report_id=db_report.id,
                    ingestion_id=ingestion_id,
                    source_name=source_name
                )
                db.add(new_event)
                success_count += 1
            except Exception:
                continue
        
        db.commit()
        return {
            "status": "success",
            "message": f"Ingesta completada: {success_count} registros cargados.",
            "report_id": db_report.id,
            "ingestion_id": ingestion_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando ingesta: {str(e)}")

@router.get("/policia/history")
def list_sabana_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(ingestion_operator),
):
    from db.models_hechos_seguridad import IngestionRun

    safe_limit = max(1, min(limit, 200))
    runs = db.query(IngestionRun).filter(
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).order_by(IngestionRun.fecha_inicio.desc()).limit(safe_limit).all()
    return {
        "items": [
            {
                "id": str(run.id),
                "filename": run.filename,
                "hash_archivo": run.hash_archivo,
                "fecha_inicio": run.fecha_inicio.isoformat() if run.fecha_inicio else None,
                "fecha_fin": run.fecha_fin.isoformat() if run.fecha_fin else None,
                "usuario_carga": run.usuario_carga,
                "total_filas": run.total_filas,
                "aprobadas": run.aprobadas,
                "rechazadas": run.rechazadas,
                "duplicadas": run.duplicadas,
                "resumen": run.resumen or {},
            }
            for run in runs
        ]
    }


@router.get("/policia/history/{run_id}/rows")
def get_sabana_snapshot_rows(
    run_id: str,
    anio: Optional[int] = None,
    semana_hasta: Optional[int] = None,
    offset: int = 0,
    limit: int = 5000,
    db: Session = Depends(get_db),
    current_user: User = Depends(ingestion_operator),
):
    from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow

    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Entrega SABANA no encontrada")

    run = db.query(IngestionRun).filter(
        IngestionRun.id == run_uuid,
        IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
        IngestionRun.status == "COMPLETED",
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Entrega SABANA no encontrada")

    query = db.query(SabanaSnapshotRow).filter(SabanaSnapshotRow.ingestion_id == run.id)
    if anio is not None:
        query = query.filter(SabanaSnapshotRow.anio == anio)
    if semana_hasta is not None:
        query = query.filter(SabanaSnapshotRow.semana_num <= semana_hasta)

    total = query.count()
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, 10000))
    rows = query.order_by(
        SabanaSnapshotRow.fecha_evento,
        SabanaSnapshotRow.record_key,
    ).offset(safe_offset).limit(safe_limit).all()

    return {
        "ingestion_id": str(run.id),
        "filename": run.filename,
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "rows": [
            {
                "record_key": row.record_key,
                "hecho_key": row.hecho_key,
                "HECHOS_ID": row.id_fuente,
                "AÑO": row.anio,
                "MES": (row.datos_normalizados or {}).get("mes", ""),
                "NoSEMANA": row.semana_num,
                "FECHA_HECHO": row.fecha_evento.isoformat(),
                "CONDUCTA": row.conducta_estandar,
                "CONDUCTA_ORIGINAL": row.conducta_original,
                "BARRIO": row.barrio_normalizado or "SIN DATO",
                "ARMA": row.arma_medio or "SIN DATO",
                "DIA": row.dia_semana or "SIN DATO",
                "GENERO": row.sexo,
                "EDAD": row.edad,
            }
            for row in rows
        ],
    }

@router.get("/runs/{run_id}", dependencies=[Depends(ingestion_operator)])
def get_ingestion_run(run_id: str, db: Session = Depends(get_db)):
    from db.models_hechos_seguridad import IngestionRun
    run = db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    return run

@router.get("/runs/{run_id}/issues", dependencies=[Depends(ingestion_operator)])
def get_ingestion_issues(run_id: str, db: Session = Depends(get_db)):
    from db.models_hechos_seguridad import IngestionIssue
    issues = db.query(IngestionIssue).filter(IngestionIssue.ingestion_id == run_id).all()
    return issues
