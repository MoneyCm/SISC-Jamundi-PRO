"""Asesor SISC: preguntas de la dirección respondidas con cifras oficiales verificadas."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from api.auth import log_audit, require_role
from db.models import User, get_db
from services import asistente_secretaria as asesor

router = APIRouter()
ROLES = ["DIRECTIVE", "ANALYST", "FUNC_ADMIN", "TI_ADMIN", "DATA_OWNER"]


class Mensaje(BaseModel):
    rol: str = Field(pattern="^(usuario|asesor)$")
    texto: str = Field(max_length=4000)


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=2, max_length=500)
    historial: List[Mensaje] = Field(default_factory=list, max_length=12)

    @field_validator('pregunta', mode='before')
    @classmethod
    def limpiar_pregunta(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.get("/sugerencias")
def sugerencias_iniciales(current_user: User = Depends(require_role(ROLES))):
    return {"sugerencias": asesor.SUGERENCIAS_INICIALES}


@router.post("/preguntar")
async def preguntar(datos: Pregunta, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(ROLES))):
    try:
        resultado = await asesor.responder(db, datos.pregunta.strip(), [m.model_dump() for m in datos.historial])
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    await log_audit(db, "ASESOR_CONSULTA", actor_id=str(current_user.id), module="asistente",
                    target={"pregunta": datos.pregunta[:200], "redactada_por": resultado.get("redactada_por"),
                            "temas": resultado.get("temas"), "resultado": asesor.clasificar(resultado),
                            "respuesta": (resultado.get("respuesta") or "")[:300]},
                    level=2, request=request)
    resultado.pop("problemas", None)
    return resultado


REVISORES = ["ANALYST", "FUNC_ADMIN", "TI_ADMIN"]


@router.get("/revision")
def revision(dias: int = 30, db: Session = Depends(get_db), current_user: User = Depends(require_role(REVISORES))):
    """Preguntas al Asesor de los últimos días que no entendió o no pudo responder, para enseñarle."""
    from datetime import datetime, timedelta
    from db.models_auth import AuditLog

    dias = max(1, min(dias, 180))
    filas = (db.query(AuditLog.created_at, AuditLog.target_ref)
             .filter(AuditLog.action == "ASESOR_CONSULTA", AuditLog.created_at >= datetime.utcnow() - timedelta(days=dias))
             .order_by(AuditLog.created_at.desc()).all())
    return asesor.resumen_revision([(fecha, target or {}) for fecha, target in filas], dias)
