"""Comisarías de Familia: carga de casos de violencia intrafamiliar (anonimizados) y análisis.

Solo se exponen agregados: ningún endpoint devuelve casos uno por uno.
"""
from datetime import date
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.auth import institutional_access, log_audit, require_role
from db.models import User, get_db
from services import vif_cases as service

router = APIRouter()

LOADER_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN", "SOURCE_UPLOADER", "STEWARD"]
MAX_BYTES = 20 * 1024 * 1024


class RemapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping: Dict[str, Optional[str]]


def _errors(call):
    try:
        return call()
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/catalog")
def catalog(current_user: User = Depends(institutional_access)):
    return service.catalog()


@router.get("/template")
def template(current_user: User = Depends(institutional_access)):
    return Response(service.template_xlsx(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="plantilla_casos_vif_comisarias.xlsx"'})


@router.get("/analysis")
def analysis(entity: Optional[str] = Query(default=None, max_length=120), start: Optional[date] = None,
             end: Optional[date] = None, db: Session = Depends(get_db),
             current_user: User = Depends(institutional_access)):
    if start and end and start > end:
        raise HTTPException(422, "La fecha inicial es posterior a la final.")
    return service.analysis(db, entity, start, end)


@router.get("/deliveries")
def deliveries(db: Session = Depends(get_db), current_user: User = Depends(require_role(LOADER_ROLES))):
    return service.list_deliveries(db)


@router.get("/deliveries/{delivery_id}")
def delivery(delivery_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_role(LOADER_ROLES))):
    return _errors(lambda: service.open_delivery(db, delivery_id))


@router.post("/deliveries/preview")
async def preview(request: Request, file: UploadFile = File(...), entity: str = Form(...),
                  db: Session = Depends(get_db), current_user: User = Depends(require_role(LOADER_ROLES))):
    content = await file.read()
    if not content:
        raise HTTPException(400, "El archivo está vacío.")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "El archivo supera 20 MB.")
    name = file.filename or "entrega.xlsx"
    if not name.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(415, "Use un archivo Excel (.xlsx) o CSV.")
    try:
        result = service.preview(db, content, name, entity, current_user.username)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:  # archivo ilegible
        raise HTTPException(422, f"No se pudo leer el archivo: {error}") from error
    await log_audit(db, "VIF_DELIVERY_PREVIEW", actor_id=str(current_user.id), module="COMISARIAS",
                    target={"id": result["id"], "entity": entity, "rows": result["summary"]["total_rows"],
                            "dropped_columns": len(result["dropped_columns"])}, level=2, request=request)
    return result


@router.put("/deliveries/{delivery_id}/mapping")
def remap(delivery_id: str, payload: RemapRequest, db: Session = Depends(get_db),
          current_user: User = Depends(require_role(LOADER_ROLES))):
    return _errors(lambda: service.remap(db, delivery_id, payload.mapping))


@router.post("/deliveries/{delivery_id}/confirm")
async def confirm(delivery_id: str, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_role(LOADER_ROLES))):
    result = _errors(lambda: service.confirm(db, delivery_id, current_user.username))
    await log_audit(db, "VIF_DELIVERY_CONFIRMED", actor_id=str(current_user.id), module="COMISARIAS",
                    target={"id": delivery_id, "entity": result["entity"], "created": result["summary"].get("created"),
                            "updated": result["summary"].get("updated")}, level=2, request=request)
    return result


@router.post("/deliveries/{delivery_id}/discard")
async def discard(delivery_id: str, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(require_role(LOADER_ROLES))):
    result = _errors(lambda: service.discard(db, delivery_id, current_user.username))
    await log_audit(db, "VIF_DELIVERY_DISCARDED", actor_id=str(current_user.id), module="COMISARIAS",
                    target={"id": delivery_id}, level=2, request=request)
    return result
