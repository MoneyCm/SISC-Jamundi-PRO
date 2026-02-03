from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
import logging
import traceback

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sisc_api")

from api import analitica, ingesta, auth, reportes
from db.models import create_tables

# Crear tablas al iniciar
create_tables()

app = FastAPI(title="SISC Jamundí API", version="0.1.0")

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
    logger.error(f"Error fatal: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"} # Forzar CORS en errores
    )

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "SISC Jamundí API is running"}

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(analitica.router, prefix="/analitica", tags=["analitica"])
app.include_router(ingesta.router, prefix="/ingesta", tags=["ingesta"])
app.include_router(reportes.router, prefix="/reportes", tags=["reportes"])

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
