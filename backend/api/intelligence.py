from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from db.models import get_db
from db.models_intelligence import NationalCrimeStats, IngestionLog
from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import logging
from datetime import datetime

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])
logger = logging.getLogger("sisc_api")

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
            for record_dict in processor.process_excel(content, file_info['name']):
                # Crear instancia de modelo
                db_record = NationalCrimeStats(**record_dict)
                records.append(db_record)
            
            if records:
                # Bulk save
                db_bg.bulk_save_objects(records)
                db_bg.commit()
                total_inserted += len(records)
            
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
    Retorna estadísticas comparativas (Stub).
    """
    # Aquí iría la consulta real a NationalCrimeStats
    # Por ahora devolvemos un mock para validar el endpoint
    return {
        "municipio": municipio,
        "anio": anio,
        "data": [
            {"delito": "Homicidio", "local": 12, "nacional_avg": 25},
            {"delito": "Hurto", "local": 150, "nacional_avg": 300}
        ]
    }
