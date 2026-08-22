# SISC Jamundí - Sistema de Información para la Seguridad
# Last Deployment Trigger: 2026-02-27 11:45
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
import logging
import traceback
import os
import uuid
from dotenv import load_dotenv
from core.config import get_cors_origins

# Cargar variables de entorno desde .env (Solo para local)
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sisc_api")

from api import analitica, ingesta, auth, reportes, ia, intelligence, participacion, dq, mindefensa, users, policia, inspecciones, institutional_indicators, sisc_cifras, source_center
logger.info(f"DEBUG: Intelligence module from: {intelligence.__file__}")
from db.models import create_tables
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciamos las migraciones en un hilo separado para NO bloquear el inicio del servidor.
    # Esto es CRÍTICO para Render, ya que si la BD tarda en conectar, Render mata el proceso por "Port scan timeout".
    import threading
    
    def run_migrations_task():
        try:
            logger.info("[Iniciando] Verificando esquema de base de datos en segundo plano...")
            create_tables()
            logger.info("[OK] Tablas verificadas.")
            
            from create_roles_v2 import init_db
            init_db()
            logger.info("[OK] Roles y usuarios inicializados.")

            # AUTO-INGESTA: Cargar datos históricos desde los CSVs si faltan
            try:
                from db.models_intelligence import NationalCrimeStats
                from db.session import SessionLocal
                db = SessionLocal()
                # Solo ejecutar si no hay datos para evitar el escaneo lento en cada inicio
                has_data = db.query(NationalCrimeStats).first() is not None
                db.close()

                if not has_data:
                    from ingest_high_impact_2025 import run_full_ingestion
                    logger.info("[Iniciando] Ingesta automática de datos históricos (Tabla vacía)...")
                    run_full_ingestion()
                    logger.info("[OK] Ingesta completada.")
                else:
                    logger.info("[INFO] Saltando ingesta automática: Los datos históricos ya existen.")
            except Exception as e_ing:
                logger.warning(f"[AVISO] Fallo en la comprobación/ingesta automática: {e_ing}")

        except Exception as e:
            logger.error(f"[ERROR] Fallo en la inicialización de BD: {e}")
            logger.error(traceback.format_exc())

    # Lanzar en modo daemon para que no bloquee el apagado si algo sale mal
    logger.info("Lanzando tarea de inicialización en segundo plano...")
    threading.Thread(target=run_migrations_task, daemon=True).start()
    
    yield

app = FastAPI(title="SISC Jamundí - Sistema de Información para la Seguridad", version="0.1.0", lifespan=lifespan)

# Loguear variables de entorno críticas (sin contraseñas) para depuración
logger.info(f"DATABASE_URL configurada: {'SÍ' if os.getenv('DATABASE_URL') else 'NO'}")
logger.info(f"PORT configurado: {os.getenv('PORT')}")

# Logger middleware para ver peticiones en terminal
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Petición recibida: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Respuesta enviada: Status {response.status_code}")
    return response

# Capturador global de errores para depuración
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    
    incident_id = uuid.uuid4().hex[:12]
    logger.exception(
        "Error no controlado [%s] en %s %s",
        incident_id,
        request.method,
        request.url.path,
    )

    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "incident_id": incident_id, "traceback": "".join(tb)},
    )

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "SISC Jamundí API is running", "commit": "8fb59aa"}

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(analitica.router, prefix="/api/analitica", tags=["analitica"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["reportes"])
app.include_router(ia.router, prefix="/api/ia", tags=["ia"])
app.include_router(ingesta.router, prefix="/api/ingesta", tags=["ingesta"])
app.include_router(mindefensa.router, prefix="/api/mindefensa", tags=["mindefensa"])
app.include_router(policia.router, prefix="/api/policia", tags=["policia"])
app.include_router(participacion.router, prefix="/api/participacion", tags=["participacion"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(dq.router, prefix="/api/dq", tags=["dq"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(inspecciones.router, prefix="/api/inspecciones", tags=["inspecciones"])
app.include_router(institutional_indicators.router, prefix="/api/institutional-indicators", tags=["institutional-indicators"])
app.include_router(sisc_cifras.router, prefix="/api/sisc-cifras", tags=["sisc-cifras"])
app.include_router(source_center.router, prefix="/api/source-center", tags=["source-center"])

# --- Fase 1.5: Router v1 para contrato aprobado ---
from api import sisc_cifras_v1
app.include_router(sisc_cifras_v1.router, prefix="/api/sisc-cifras", tags=["sisc-cifras-v1"])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
