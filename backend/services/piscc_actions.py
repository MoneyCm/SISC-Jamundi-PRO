"""Seguimiento semestral del plan de acción del PISCC 2024-2027 (43 acciones, 4 vectores).

Cada semestre las entidades del Comité Territorial de Orden Público reportan el avance de sus
acciones (PISCC 9.1). Aquí se arma el tablero: avance de cada acción frente a su meta del
cuatrienio, resumen por vector, qué entidades no han reportado y la exportación para el SisPT.

Reglas:
- El avance es acumulado del cuatrienio; si una acción no reportó en el semestre, se muestra su
  último reporte anterior, señalado como tal (no se da por cero ni por reportado).
- El porcentaje de avance se topa en 100 %.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models_piscc import PisccActionReport

CATALOG = Path(__file__).resolve().parents[1] / "data" / "piscc" / "acciones_2024_2027.json"
FIRST_SEMESTER, LAST_SEMESTER = "2024-1", "2027-2"


@lru_cache(maxsize=1)
def load_catalog() -> Dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def semester_of(day: date) -> str:
    return f"{day.year}-{1 if day.month <= 6 else 2}"


def previous_semester(semester: str) -> str:
    year, half = int(semester[:4]), int(semester[5])
    return f"{year}-1" if half == 2 else f"{year - 1}-2"


def plan_semesters() -> List[str]:
    return [f"{year}-{half}" for year in range(2024, 2028) for half in (1, 2)]


def valid_semester(semester: str) -> bool:
    return semester in plan_semesters()


def month_in_semester(day: date) -> int:
    return (day.month - 1) % 6 + 1


def lead_entity(responsible: str) -> str:
    """La primera entidad nombrada responde el reporte (las demás acompañan)."""
    return responsible.split(" – ")[0].strip()


def progress_pct(value: Optional[float], goal: float) -> Optional[float]:
    if value is None or not goal:
        return None
    return round(min(value / goal, 1.0) * 100, 1)


def serialize_report(row: PisccActionReport) -> Dict[str, Any]:
    return {
        "semester": row.semester, "value": row.value, "status": row.status,
        "reporting_entity": row.reporting_entity, "evidence": row.evidence, "note": row.note,
        "received_on": row.received_on.isoformat() if row.received_on else None,
        "updated_by": row.updated_by or row.created_by, "version": row.version,
    }


def build_tracking(db: Session, semester: str) -> Dict[str, Any]:
    catalog = load_catalog()
    rows = db.query(PisccActionReport).filter(PisccActionReport.semester <= semester).all()
    by_action: Dict[str, List[PisccActionReport]] = {}
    for row in rows:
        by_action.setdefault(row.action_code, []).append(row)

    actions = []
    for item in catalog["actions"]:
        history = sorted(by_action.get(item["code"], []), key=lambda row: row.semester)
        current = next((row for row in history if row.semester == semester), None)
        latest = current or (history[-1] if history else None)
        actions.append({
            **item,
            "lead_entity": lead_entity(item["responsible"]),
            "report": serialize_report(current) if current else None,
            "last_report": serialize_report(latest) if latest and not current else None,
            "progress_pct": progress_pct(latest.value if latest else None, item["goal"]),
            "reported": current is not None,
        })

    vectors = []
    for vector in catalog["vectors"]:
        items = [action for action in actions if action["vector"] == vector["code"]]
        known = [action["progress_pct"] for action in items if action["progress_pct"] is not None]
        vectors.append({
            **vector,
            "actions": len(items),
            "reported": sum(action["reported"] for action in items),
            "completed": sum(1 for action in items if (action["report"] or action["last_report"] or {}).get("status") == "CUMPLIDA"),
            "average_progress": round(sum(known) / len(items), 1) if items else None,
            "with_progress": len(known),
        })

    pending: Dict[str, List[str]] = {}
    for action in actions:
        if not action["reported"]:
            pending.setdefault(action["lead_entity"], []).append(action["code"])

    return {
        "semester": semester,
        "semesters": plan_semesters(),
        "plan": catalog["plan"],
        "source": catalog["source"],
        "transcription": catalog["transcription"],
        "vectors": vectors,
        "actions": actions,
        "totals": {
            "actions": len(actions),
            "reported": sum(action["reported"] for action in actions),
            "completed": sum(vector["completed"] for vector in vectors),
        },
        "pending_by_entity": [{"entity": entity, "actions": codes}
                              for entity, codes in sorted(pending.items(), key=lambda pair: (-len(pair[1]), pair[0]))],
        "rule": ("Avance acumulado del cuatrienio frente a la meta de cada acción, topado en 100 %. "
                 "Si una acción no reportó en el semestre se muestra su último reporte, señalado como tal; "
                 "el promedio del vector cuenta como 0 las acciones que nunca han reportado."),
    }


CSV_COLUMNS = ("Código", "Vector", "Responsable", "Acción estratégica", "Indicador de producto", "Meta cuatrienio",
               "Semestre", "Avance acumulado", "% de avance", "Estado", "Reportó en el semestre",
               "Entidad que reporta", "Fecha de recibo", "Soporte", "Observación")


def export_csv(tracking: Dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(CSV_COLUMNS)
    for action in tracking["actions"]:
        report = action["report"] or action["last_report"] or {}
        writer.writerow([
            action["code"], action["vector"], action["responsible"], action["action"], action["indicator"],
            action["goal"], report.get("semester") or tracking["semester"],
            "" if report.get("value") is None else str(report["value"]).replace(".", ","),
            "" if action["progress_pct"] is None else str(action["progress_pct"]).replace(".", ","),
            report.get("status") or "SIN_REPORTE", "Sí" if action["reported"] else "No",
            report.get("reporting_entity") or "", report.get("received_on") or "",
            report.get("evidence") or "", report.get("note") or "",
        ])
    return "﻿" + buffer.getvalue()  # BOM: Excel abre las tildes bien


def signals(db: Session, today: date) -> List[Dict[str, Any]]:
    """Meses 5 y 6 del semestre: pedir y consolidar. Mes 1 del siguiente: si quedó incompleto, atrasado."""
    month = month_in_semester(today)
    if month in (5, 6):
        semester, late = semester_of(today), False
    elif month == 1:
        semester, late = previous_semester(semester_of(today)), True
    else:
        return []
    if not valid_semester(semester):
        return []
    totals = build_tracking(db, semester)["totals"]
    missing = totals["actions"] - totals["reported"]
    if not missing:
        return [{"level": "OK", "title": f"Seguimiento del PISCC {semester} completo",
                 "detail": f"Las {totals['actions']} acciones reportaron avance del semestre."}]
    if late:
        return [{"level": "ALTA", "title": f"Seguimiento del PISCC {semester} incompleto",
                 "detail": f"{missing} de {totals['actions']} acciones sin reporte del semestre que cerró.", "count": missing}]
    return [{"level": "MEDIA", "title": f"Seguimiento semestral del PISCC: {missing} acciones sin reporte",
             "detail": f"Semestre {semester}: pida el avance a las entidades responsables (PISCC 9.1).", "count": missing}]
