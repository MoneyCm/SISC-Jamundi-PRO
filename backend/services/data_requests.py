"""Solicitudes de datos: a quién se pidió qué, cuándo, y si respondió.

Estados de una dependencia, según su periodicidad (semanal, quincenal, mensual):
- ESPERANDO: hay una solicitud abierta dentro del plazo.
- ATRASADA: hay una solicitud abierta con el plazo vencido.
- AL_DIA: respondió dentro de su periodicidad (con unos días de gracia).
- TOCA_PEDIR: no hay solicitud abierta y la última respuesta ya es vieja (o nunca hubo).

Junto a cada dependencia se muestra el último corte cargado en el SISC (lotes institucionales),
que confirma si lo recibido llegó de verdad al sistema.
"""
from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models_data_requests import DataEntity, DataRequest

CADENCE_DAYS = {"SEMANAL": 7, "QUINCENAL": 14, "MENSUAL": 31}
GRACE_DAYS = {"SEMANAL": 3, "QUINCENAL": 4, "MENSUAL": 7}
DEFAULT_DUE_DAYS = 3
VERY_LATE_DAYS = 21
DEFAULT_ENTITIES = (
    ("Inspección Tercera de Policía", "INSPECCIONES", "SEMANAL"),
    ("Comisaría Primera de Familia", "COMISARIAS", "MENSUAL"),
    ("Comisaría Segunda de Familia", "COMISARIAS", "MENSUAL"),
)
STOPWORDS = {"DE", "LA", "EL", "POLICIA", "FAMILIA"}
STATE_ORDER = {"ATRASADA": 0, "TOCA_PEDIR": 1, "ESPERANDO": 2, "AL_DIA": 3}


def match_key(name: Optional[str]) -> str:
    """'Inspección Tercera de Policía' y 'Inspeccion Tercera' son la misma dependencia."""
    text = unicodedata.normalize("NFD", name or "").encode("ascii", "ignore").decode().upper()
    return " ".join(word for word in text.replace("-", " ").split() if word not in STOPWORDS)


def ensure_defaults(db: Session) -> None:
    if db.query(DataEntity.id).first():
        return
    for name, program, cadence in DEFAULT_ENTITIES:
        db.add(DataEntity(name=name, program=program, cadence=cadence))
    db.commit()


def loaded_cutoffs(db: Session) -> Dict[str, Dict[str, Any]]:
    """Último corte cargado por dependencia, desde los lotes institucionales no rechazados."""
    from db.models_institutional import InstitutionalDataBatch

    rows = db.query(InstitutionalDataBatch.reporting_entity, func.max(InstitutionalDataBatch.cutoff_date),
                    func.max(InstitutionalDataBatch.created_at)).filter(
        InstitutionalDataBatch.validation_status != "REJECTED").group_by(InstitutionalDataBatch.reporting_entity).all()
    result: Dict[str, Dict[str, Any]] = {}
    for entity, cutoff, loaded_at in rows:
        key = match_key(entity)
        current = result.get(key)
        if not current or (cutoff and cutoff > current["cutoff"]):
            result[key] = {"cutoff": cutoff, "loaded_on": loaded_at.date() if loaded_at else None}
    return result


def entity_state(cadence: str, requests: Iterable[DataRequest], today: date) -> Dict[str, Any]:
    requests = list(requests)
    open_requests = [row for row in requests if row.status == "PEDIDA"]
    answered = [row.received_on for row in requests if row.status in ("RECIBIDA", "INCOMPLETA") and row.received_on]
    last_received = max(answered) if answered else None
    base = {"last_received": last_received.isoformat() if last_received else None,
            "days_since_received": (today - last_received).days if last_received else None}
    if open_requests:
        oldest = min(open_requests, key=lambda row: row.requested_on)
        due = min(row.due_on for row in open_requests)
        info = {**base, "open_since": oldest.requested_on.isoformat(), "due_on": due.isoformat(),
                "days_waiting": (today - oldest.requested_on).days}
        if due < today:
            return {**info, "state": "ATRASADA", "days_late": (today - due).days}
        return {**info, "state": "ESPERANDO"}
    limit = CADENCE_DAYS.get(cadence, 7) + GRACE_DAYS.get(cadence, 3)
    if last_received and (today - last_received).days <= limit:
        return {**base, "state": "AL_DIA"}
    return {**base, "state": "TOCA_PEDIR"}


def serialize_request(row: DataRequest, entity_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": str(row.id), "entity_id": str(row.entity_id), "entity": entity_name, "what": row.what,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "requested_on": row.requested_on.isoformat(), "due_on": row.due_on.isoformat(),
        "channel": row.channel, "status": row.status,
        "received_on": row.received_on.isoformat() if row.received_on else None,
        "note": row.note, "created_by": row.created_by, "updated_by": row.updated_by, "version": row.version,
    }


def board(db: Session, today: Optional[date] = None, include_inactive: bool = False) -> Dict[str, Any]:
    today = today or date.today()
    ensure_defaults(db)
    query = db.query(DataEntity)
    if not include_inactive:
        query = query.filter(DataEntity.active.is_(True))
    entities = query.order_by(DataEntity.program, DataEntity.name).all()
    requests = db.query(DataRequest).filter(DataRequest.entity_id.in_([entity.id for entity in entities])).all() if entities else []
    loaded = loaded_cutoffs(db)
    rows = []
    for entity in entities:
        own = [row for row in requests if row.entity_id == entity.id]
        state = entity_state(entity.cadence, own, today)
        data = loaded.get(match_key(entity.name))
        rows.append({
            "id": str(entity.id), "name": entity.name, "program": entity.program, "cadence": entity.cadence,
            "contact": entity.contact, "active": entity.active, **state,
            "loaded_cutoff": data["cutoff"].isoformat() if data and data["cutoff"] else None,
            "open_requests": [serialize_request(row, entity.name) for row in sorted(own, key=lambda r: r.requested_on) if row.status == "PEDIDA"],
        })
    rows.sort(key=lambda row: (STATE_ORDER[row["state"]], row["name"]))
    names = {entity.id: entity.name for entity in entities}
    recent = sorted(requests, key=lambda row: (row.requested_on, row.created_at), reverse=True)[:30]
    return {
        "as_of": today.isoformat(),
        "entities": rows,
        "recent": [serialize_request(row, names.get(row.entity_id)) for row in recent],
        "counts": {state: sum(1 for row in rows if row["state"] == state) for state in STATE_ORDER},
        "rule": ("Una dependencia está al día si respondió dentro de su periodicidad (semanal: 10 días, quincenal: 18, "
                 "mensual: 38). Una solicitud abierta se vuelve atrasada al vencer su plazo."),
    }


def _ago(days: int) -> str:
    if days < 14:
        return f"{days} días"
    return f"{days // 7} semanas"


def signals(db: Session, today: date) -> List[Dict[str, Any]]:
    data = board(db, today)
    rows: List[Dict[str, Any]] = []
    for entity in data["entities"]:
        if entity["state"] != "ATRASADA":
            continue
        if entity["days_since_received"] is not None:
            title = f"{entity['name']} sin reportar hace {_ago(entity['days_since_received'])}"
        else:
            title = f"{entity['name']} no ha respondido la solicitud del {date.fromisoformat(entity['open_since']):%d/%m}"
        level = "ALTA" if entity["days_waiting"] > VERY_LATE_DAYS else "MEDIA"
        rows.append({"level": level, "title": title, "count": entity["days_late"],
                     "detail": f"El plazo venció el {date.fromisoformat(entity['due_on']):%d/%m/%Y}; lleva {entity['days_waiting']} días esperando."})
    due = [entity["name"] for entity in data["entities"] if entity["state"] == "TOCA_PEDIR"]
    if due:
        rows.append({"level": "MEDIA", "title": f"Toca pedir datos a {len(due)} {'dependencia' if len(due) == 1 else 'dependencias'}",
                     "detail": ", ".join(due) + ".", "count": len(due)})
    if not rows and data["entities"]:
        rows.append({"level": "OK", "title": "Solicitudes de datos al día",
                     "detail": f"{len(data['entities'])} dependencias respondieron o están dentro del plazo."})
    return rows
