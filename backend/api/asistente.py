"""Asesor SISC: preguntas de la dirección respondidas con cifras oficiales verificadas."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
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
                            "temas": resultado.get("temas")},
                    level=2, request=request)
    resultado.pop("problemas", None)
    return resultado
