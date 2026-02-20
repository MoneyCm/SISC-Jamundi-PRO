from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from db.models import get_db
from api.auth import get_current_user
from db.models import User
from db.models_intelligence import NationalCrimeStats, IngestionLog
from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import logging
from datetime import datetime

router = APIRouter(tags=["Intelligence"])
logger = logging.getLogger("sisc_api")

@router.post("/upload")
async def upload_intelligence_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Carga manual de archivos Excel de MinDefensa.
    Procesa el archivo y carga los datos en la base de datos.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos Excel (.xlsx, .xls)")

    # Crear log de inicio
    log_entry = IngestionLog(
        estado="IN_PROGRESS",
        registros_insertados=0,
        errores=None,
        detalles={"filename": file.filename}
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    try:
        contents = await file.read()
        processor = NationalStatsProcessor()
        
        # Procesar generator
        records_generator = processor.process_excel(contents, file.filename)
        
        count = 0
        batch = []
        BATCH_SIZE = 1000
        
        for record in records_generator:
            # Crear modelo
            db_record = NationalCrimeStats(**record)
            batch.append(db_record)
            
            if len(batch) >= BATCH_SIZE:
                db.bulk_save_objects(batch)
                db.commit()
                count += len(batch)
                batch = []
        
        # Guardar remanente
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            count += len(batch)
            
        # Actualizar log exitoso
        log_entry.estado = "SUCCESS"
        log_entry.registros_insertados = count
        log_entry.fecha_fin = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Archivo procesado exitosamente",
            "filename": file.filename,
            "records_inserted": count
        }
        
    except Exception as e:
        # Log error
        log_entry.estado = "ERROR"
        log_entry.errores = str(e)
        log_entry.fecha_fin = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")

@router.post("/ingest")
async def trigger_ingestion(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Inicia el proceso de descarga e ingesta de datos nacionales en segundo plano.
    """
    # Crear log de inicio
    log_entry = IngestionLog(estado="IN_PROGRESS", detalles={"trigger": "manual"})
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    
    background_tasks.add_task(run_ingestion_process, log_entry.id, db)
    
    return {"status": "started", "log_id": log_entry.id, "message": "Ingesta iniciada en segundo plano"}

def run_ingestion_process(log_id: int, db: Session): # Session here might be closed if not handled carefully in background
    # Re-instantiate session or use a new one is better practice for background tasks, 
    # but for simplicity we'll try to use a new session factory if possible.
    # Actually, Dependency injection session is closed after request. 
    # So we should create a new session here.
    from db.models import SessionLocal
    db_bg = SessionLocal()
    
    try:
        log = db_bg.query(IngestionLog).get(log_id)
        scraper = MinDefensaScraper()
        processor = NationalStatsProcessor()
        
        files = scraper.fetch_available_files()
        log.detalles = {"found_files": len(files), "file_list": [f['name'] for f in files]}
        db_bg.commit()
        
        total_inserted = 0
        processed_files = 0
        
        for file_info in files:
            # Descargar
            content = scraper.download_file(file_info['url'])
            if not content:
                continue
                
            # Procesar
            # Convertir generador a lista para inserción masiva (bulk es mejor)
            records = []
            inferred_delito = file_info.get('category')
            
            for record_dict in processor.process_excel(content, file_info['name'], inferred_delito):
                # Crear instancia de modelo
                db_record = NationalCrimeStats(**record_dict)
                records.append(db_record)
            
            if records:
                # Bulk save with duplicate prevention handling
                try:
                    # Usamos una técnica de "insert ignore" o similar si el DB lo soporta, 
                    # o simplemente capturamos la excepción de integridad.
                    # SQL Alchemy bulk_save_objects no maneja bien ON CONFLICT.
                    # Por ahora, insertamos uno a uno o capturamos el error del batch.
                    db_bg.bulk_save_objects(records)
                    db_bg.commit()
                    total_inserted += len(records)
                except Exception as batch_err:
                    db_bg.rollback()
                    logger.warning(f"Error en batch de {file_info['name']}, intentando inserción individual: {batch_err}")
                    # Fallback a inserción individual para ignorar duplicados
                    for r in records:
                        try:
                            db_bg.add(r)
                            db_bg.commit()
                            total_inserted += 1
                        except Exception:
                            db_bg.rollback() # Ignorar duplicado (hash_registro unique constraint)
                            continue
            
            processed_files += 1
            
        log.estado = "SUCCESS"
        log.archivos_procesados = processed_files
        log.registros_insertados = total_inserted
        log.fecha_fin = datetime.utcnow()
        db_bg.commit()
        
    except Exception as e:
        logger.error(f"Error crítico en ingesta background: {e}")
        if log:
            log.estado = "ERROR"
            log.errores = str(e)
            log.fecha_fin = datetime.utcnow()
            db_bg.commit()
    finally:
        db_bg.close()

@router.get("/stats")
async def get_national_stats(municipio: str = "JAMUNDI", anio: int = 2025, db: Session = Depends(get_db)):
    """
    Retorna estadísticas comparativas reales basadas en los datos cargados.
    """
    from sqlalchemy import func
    
    # 1. Normalizar municipio
    processor = NationalStatsProcessor()
    target_municipio = processor.normalize_text(municipio)
    
    # 2. Obtener datos locales (Jamundí o el seleccionado)
    local_data = db.query(
        NationalCrimeStats.tipo_delito,
        func.sum(NationalCrimeStats.cantidad).label("total")
    ).filter(
        NationalCrimeStats.municipio_normalizado == target_municipio,
        NationalCrimeStats.anio == anio
    ).group_by(NationalCrimeStats.tipo_delito).all()

    # 3. Obtener promedios nacionales por delito para el mismo año
    # Calculamos el promedio de todos los municipios reportados
    national_avg_data = db.query(
        NationalCrimeStats.tipo_delito,
        func.avg(NationalCrimeStats.cantidad).label("avg") # Promedio por entrada 
    ).filter(
        NationalCrimeStats.anio == anio
    ).group_by(NationalCrimeStats.tipo_delito).all()
    
    # Convertir a dict para fácil acceso
    avg_dict = {row.tipo_delito: float(row.avg) for row in national_avg_data}
    
    # 4. Tendencia mensual local
    trend_data = db.query(
        NationalCrimeStats.mes,
        func.sum(NationalCrimeStats.cantidad).label("total")
    ).filter(
        NationalCrimeStats.municipio_normalizado == target_municipio,
        NationalCrimeStats.anio == anio
    ).group_by(NationalCrimeStats.mes).order_by(NationalCrimeStats.mes).all()

    # Formatear respuesta
    result_data = []
    for row in local_data:
        result_data.append({
            "delito": row.tipo_delito,
            "local": int(row.total),
            "nacional_avg": round(avg_dict.get(row.tipo_delito, 0), 2)
        })

    return {
        "municipio": municipio,
        "anio": anio,
        "summary": result_data,
        "trend": [{"mes": row.mes, "cantidad": int(row.total)} for row in trend_data]
    }
