from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, UploadFile, File
from sqlalchemy.orm import Session # Rebuild v2
from db.models import get_db
from api.auth import get_current_user
from db.models import User
from db.models_intelligence import NationalCrimeStats, IngestionLog
from services.scraper_mindefensa import MinDefensaScraper
from services.excel_processor import NationalStatsProcessor
import logging
from datetime import datetime
from api.ia import call_gemini, call_mistral, AI_PROVIDER, GEMINI_API_KEY, MISTRAL_API_KEY

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
    # Importante: refrescar para asegurarnos que ID existe y la DB hizo flush/commit completo
    db.refresh(log_entry)
    log_id = log_entry.id
    
    background_tasks.add_task(run_ingestion_process, log_id)
    
    return {"status": "started", "log_id": log_id, "message": "Ingesta iniciada en segundo plano"}

@router.get("/ingest/status/{log_id}")
async def get_ingestion_status(log_id: int, db: Session = Depends(get_db)):
    """
    Retorna el estado de una tarea de ingesta en background.
    """
    log_entry = db.query(IngestionLog).filter(IngestionLog.id == log_id).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log_id no encontrado")

    return {
        "id": log_entry.id,
        "estado": log_entry.estado,
        "registros_insertados": log_entry.registros_insertados,
        "archivos_procesados": log_entry.archivos_procesados,
        "errores": log_entry.errores,
        "fecha_inicio": log_entry.fecha_inicio,
        "fecha_fin": log_entry.fecha_fin,
        "detalles": log_entry.detalles
    }

def run_ingestion_process(log_id: int):
    try:
        from services.scraper_mindefensa import MinDefensaScraper
        from services.scraper_policia import PoliciaScraper
        from services.excel_processor import NationalStatsProcessor
        from db.models import SessionLocal
        
        db_bg = SessionLocal()
        
        # Wait a moment to ensure the web request transaction is fully visible
        import time
        time.sleep(1)
        
        log = db_bg.query(IngestionLog).filter(IngestionLog.id == log_id).first()
        if not log:
            logger.error(f"Error crítico: log_id {log_id} no encontrado en background task.")
            db_bg.close()
            return
            
        log.estado = 'IN_PROGRESS'
        db_bg.commit()
        
        scraper_mindefensa = MinDefensaScraper()
        scraper_policia = PoliciaScraper()
        processor = NationalStatsProcessor()
        
        # 1. Obtener archivos ya procesados exitosamente en el pasado
        processed_files_names = set()
        past_successful_logs = db_bg.query(IngestionLog).filter(
            IngestionLog.estado == 'SUCCESS',
            IngestionLog.id < log_id
        ).all()
        for p_log in past_successful_logs:
            if p_log.detalles and "processed_file_list" in p_log.detalles:
                processed_files_names.update(p_log.detalles["processed_file_list"])

        # 2. Combinar listas de archivos de ambas fuentes
        files_md = scraper_mindefensa.fetch_available_files()
        try:
            files_policia = scraper_policia.fetch_available_files()
        except Exception as e:
            logger.warning(f"No se pudieron obtener archivos de la Policía: {e}")
            files_policia = []
            
        all_remote_files = files_md + files_policia
        
        # 3. Filtrado inteligente
        current_year = datetime.now().year
        files_to_process = []
        skipped_files = []
        
        for f in all_remote_files:
            file_year = f.get('year', 2025)
            # Solo omitir si es un año pasado Y ya fue procesado con éxito
            if file_year < current_year and f['name'] in processed_files_names:
                skipped_files.append(f['name'])
            else:
                files_to_process.append(f)

        total_files = len(files_to_process)
        log.detalles = {
            "found_files": len(all_remote_files),
            "files_to_process": total_files,
            "skipped_count": len(skipped_files),
            "skipped_files": skipped_files,
            "processed_file_list": [] # Se llenará conforme se procesen
        }
        db_bg.commit()
        
        records_inserted = 0
        processed_count = 0
        total_inserted = 0
        
        processed_file_list = []
        
        for file_info in files_to_process:
            # ACTUALIZAR PROGRESO AL INICIO DE CADA ARCHIVO
            import copy
            from sqlalchemy.orm.attributes import flag_modified
            
            new_detalles = copy.deepcopy(log.detalles) if log.detalles else {}
            new_detalles["current_file"] = file_info['name']
            new_detalles["processed_files"] = processed_count 
            new_detalles["progress"] = round((processed_count / total_files) * 100) if total_files > 0 else 0
            
            log.detalles = new_detalles
            flag_modified(log, "detalles")
            db_bg.commit()
            
            logger.info(f"Iniciando procesamiento de {file_info['name']} (Progreso: {new_detalles['progress']}%)")

            # Avanzar contador para la UI
            processed_count += 1

            try:
                # Seleccionar scraper adecuado vía URL
                if 'policia.gov.co' in file_info['url']:
                    content = scraper_policia.download_file(file_info['url'])
                else:
                    content = scraper_mindefensa.download_file(file_info['url'])
                    
                if content:
                    records_generator = processor.process_excel(content, file_info['name'])
                    
                    batch = []
                    BATCH_SIZE = 500 # Un poco más conservador para evitar OOM
                    from sqlalchemy.dialects.postgresql import insert

                    for record_dict in records_generator:
                        batch.append(record_dict)
                        
                        if len(batch) >= BATCH_SIZE:
                            try:
                                stmt = insert(NationalCrimeStats).values(batch)
                                stmt = stmt.on_conflict_do_nothing(index_elements=['hash_registro'])
                                db_bg.execute(stmt)
                                db_bg.commit()
                                total_inserted += len(batch)
                            except Exception as batch_err:
                                db_bg.rollback()
                                logger.error(f"Error en bloque de {file_info['name']}: {batch_err}")
                                # Inserción individual si el bloque falla (duplicados, etc)
                                for r in batch:
                                    try:
                                        db_bg.add(NationalCrimeStats(**r))
                                        db_bg.commit()
                                        total_inserted += 1
                                    except Exception:
                                        db_bg.rollback()
                                        continue
                            batch = []
                            import gc
                            gc.collect()

                    # Guardar remanente
                    if batch:
                        try:
                            stmt = insert(NationalCrimeStats).values(batch)
                            stmt = stmt.on_conflict_do_nothing(index_elements=['hash_registro'])
                            db_bg.execute(stmt)
                            db_bg.commit()
                            total_inserted += len(batch)
                        except Exception as rem_err:
                            db_bg.rollback()
                            for r in batch:
                                try:
                                    db_bg.add(NationalCrimeStats(**r))
                                    db_bg.commit()
                                    total_inserted += 1
                                except Exception:
                                    db_bg.rollback()
                                    continue
                    
                # Liberar memoria
                if 'content' in locals(): del content
                import gc
                gc.collect()

                # Registro de éxito para este archivo
                processed_file_list.append(file_info['name'])
                log.detalles["processed_file_list"] = processed_file_list
                flag_modified(log, "detalles")
                db_bg.commit()

            except Exception as loop_err:
                logger.error(f"Error inesperado procesando archivo {file_info['name']}: {loop_err}")
            
        log.estado = "SUCCESS"
        log.archivos_procesados = processed_count
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
    # Segundo: Obtener la suma nacional total por delito para el año actual
    # Como agrupamos todos los demás en 'TOTAL_NACIONAL', el total son ~1122 municipios físicos reales en Colombia.
    total_municipios_conocidos = 1122
    
    # Segundo: Obtener la suma nacional total por delito para el año actual
    national_sums = db.query(
        NationalCrimeStats.tipo_delito,
        func.sum(NationalCrimeStats.cantidad).label("sum_total")
    ).filter(
        NationalCrimeStats.anio == anio
    ).group_by(NationalCrimeStats.tipo_delito).all()
    
    # Convertir a dict de promedios "reales" (Suma / Población total de municipios)
    avg_dict = {row.tipo_delito: (float(row.sum_total) / total_municipios_conocidos) for row in national_sums}
    
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

@router.get("/municipios")
async def get_available_municipios(db: Session = Depends(get_db)):
    """
    Retorna la lista de municipios que tienen datos cargados en el sistema.
    """
    from sqlalchemy import func
    
    # Obtener municipios únicos y ordenados
    municipios = db.query(
        NationalCrimeStats.municipio_normalizado,
        NationalCrimeStats.municipio
    ).distinct().order_by(NationalCrimeStats.municipio).all()
    
    return [
        {"id": m.municipio_normalizado, "nombre": m.municipio}
        for m in municipios
    ]

@router.get("/years")
async def get_available_years(db: Session = Depends(get_db)):
    """
    Retorna la lista de años únicos que tienen datos cargados en el sistema.
    """
    from sqlalchemy import func
    anios = db.query(NationalCrimeStats.anio).distinct().order_by(NationalCrimeStats.anio.desc()).all()
    return [a.anio for a in anios]

@router.get("/insights")
async def get_intelligence_insights(municipio: str = "JAMUNDI", anio: int = 2025, db: Session = Depends(get_db)):
    """
    Genera un análisis comparativo narrativo usando IA basado en los datos de MinDefensa.
    """
    try:
        from sqlalchemy import func
        
        # 1. Obtener los mismos datos que /stats para dar contexto a la IA
        processor = NationalStatsProcessor()
        target_municipio = processor.normalize_text(municipio)
        
        local_data = db.query(
            NationalCrimeStats.tipo_delito,
            func.sum(NationalCrimeStats.cantidad).label("total")
        ).filter(
            NationalCrimeStats.municipio_normalizado == target_municipio,
            NationalCrimeStats.anio == anio
        ).group_by(NationalCrimeStats.tipo_delito).all()

        # Nueva Lógica Refinada
        total_municipios_conocidos = 1122
        
        national_sums = db.query(
            NationalCrimeStats.tipo_delito,
            func.sum(NationalCrimeStats.cantidad).label("sum_total")
        ).filter(
            NationalCrimeStats.anio == anio
        ).group_by(NationalCrimeStats.tipo_delito).all()
        
        avg_dict = {row.tipo_delito: (float(row.sum_total) / total_municipios_conocidos) for row in national_sums}
        
        # Construir resumen para la IA
        stats_summary = ""
        for row in local_data:
            avg = avg_dict.get(row.tipo_delito, 0)
            diff = ((row.total - avg) / avg * 100) if avg > 0 else 0
            stats_summary += f"- {row.tipo_delito}: {row.total} casos (Promedio Nacional: {round(avg, 1)}, Dif: {round(diff, 1)}%)\n"

        if not stats_summary:
            return {"insight": "No hay suficientes datos disponibles para generar un análisis estratégico en este momento."}

        contexto = f"""
        Eres el Consultor Senior de Inteligencia Estratégica para el SISC Jamundí.
        Analiza la comparativa del municipio de {municipio} (Año {anio}) frente al promedio nacional de Colombia:
        
        DATOS DE INCIDENCIA:
        {stats_summary}
        
        TAREA:
        Escribe un análisis ejecutivo (máximo 80 palabras) que:
        1. Identifique los desafíos críticos (donde el municipio está por encima del promedio).
        2. Resalte aspectos positivos si los hay.
        3. Use un tono técnico, estratégico y profesional orientado a la toma de decisiones.
        4. Responde en español directo, sin introducciones innecesarias.
        5. No uses Markdown, solo texto plano.
        """

        try:
            # Validar proveedores configurados en api.ia
            if AI_PROVIDER == "MISTRAL":
                insight_text = await call_mistral(contexto)
            else:
                insight_text = await call_gemini(contexto)
                
            return {"insight": insight_text, "provider": AI_PROVIDER}
        except Exception as e:
            logger.error(f"Error generando insights de inteligencia (API IA): {e}")
            return {"insight": "Análisis estratégico no disponible temporalmente debido a un error de conexión con el motor de IA o al alcanzar el límite de la cuota gratuita.", "error": str(e)}

    except Exception as general_err:
        logger.error(f"Error estructurando datos locales para insights: {general_err}")
        return {"insight": "Error interno al preparar los datos estratégicos. Por favor verifique la conexión a la base de datos.", "error": str(general_err)}
