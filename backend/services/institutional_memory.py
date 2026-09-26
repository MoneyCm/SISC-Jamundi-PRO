"""Memoria institucional del Observatorio: lo que ya se estudió, recomendó, decidió y evaluó.

No se captura nada nuevo: reúne en un archivo consultable lo que el SISC ya guarda.
- Estudios cerrados, con hallazgos, factores asociados y la suerte de sus recomendaciones.
- Recomendaciones rechazadas (con el motivo) o cumplidas.
- Intervenciones finalizadas o evaluadas, con el resultado de la evaluación. Las finalizadas sin
  evaluar se muestran como tales: también son memoria (lo que quedó sin medir).
Los estudios reservados solo los ve el equipo de análisis.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from db.models_interventions import InterventionCase
from db.models_observatory import ObservatoryRecommendation, ObservatoryStudy

KINDS = {"ESTUDIO": "Estudio", "RECOMENDACION": "Recomendación", "INTERVENCION": "Intervención"}
SUMMARY_CHARS = 600


def fold(text: Optional[str]) -> str:
    return unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode().lower()


def _day(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _short(text: Optional[str]) -> str:
    text = (text or "").strip()
    return text if len(text) <= SUMMARY_CHARS else text[:SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"


def _last_event_day(history: List[Dict[str, Any]], status: str) -> Optional[date]:
    days = [_day(event.get("at")) for event in history or [] if event.get("status") == status]
    days = [day for day in days if day]
    return max(days) if days else None


def study_items(db: Session, include_reserved: bool) -> List[Dict[str, Any]]:
    query = db.query(ObservatoryStudy).filter(ObservatoryStudy.status == "CERRADO")
    if not include_reserved:
        query = query.filter(ObservatoryStudy.access_level != "RESERVADO")
    studies = query.all()
    recommendations: Dict[Any, List[ObservatoryRecommendation]] = {}
    if studies:
        for rec in db.query(ObservatoryRecommendation).filter(
                ObservatoryRecommendation.study_id.in_([study.id for study in studies])).order_by(ObservatoryRecommendation.code).all():
            recommendations.setdefault(rec.study_id, []).append(rec)
    items = []
    for study in studies:
        recs = recommendations.get(study.id, [])
        adopted = sum(1 for rec in recs if rec.status in ("ACEPTADA", "EN_EJECUCION", "CUMPLIDA"))
        items.append({
            "kind": "ESTUDIO", "code": study.code, "title": study.title, "date": _day(study.updated_at),
            "territory": study.territory, "phenomenon": study.phenomenon, "reserved": study.access_level == "RESERVADO",
            "summary": _short(study.findings),
            "outcome": (f"{len(recs)} recomendaciones, {adopted} adoptadas" if recs else "Sin recomendaciones"),
            "detail": {
                "question": study.question, "associated_factors": study.associated_factors,
                "period": [study.period_start.isoformat() if study.period_start else None,
                           study.period_end.isoformat() if study.period_end else None],
                "field_notes": len(study.field_notes or []),
                "review_on": study.review_on.isoformat() if study.review_on else None,
                "recommendations": [{"code": rec.code, "title": rec.title, "status": rec.status,
                                     "decision_note": rec.decision_note} for rec in recs],
            },
        })
    return items


def recommendation_items(db: Session, include_reserved: bool) -> List[Dict[str, Any]]:
    rows = db.query(ObservatoryRecommendation, ObservatoryStudy).outerjoin(
        ObservatoryStudy, ObservatoryStudy.id == ObservatoryRecommendation.study_id).filter(
        ObservatoryRecommendation.status.in_(("RECHAZADA", "CUMPLIDA"))).all()
    items = []
    for rec, study in rows:
        if study is not None and study.access_level == "RESERVADO" and not include_reserved:
            continue
        rejected = rec.status == "RECHAZADA"
        when = rec.decided_on if rejected else (_last_event_day(rec.history, "CUMPLIDA") or rec.decided_on)
        items.append({
            "kind": "RECOMENDACION", "code": rec.code, "title": rec.title,
            "date": when or _day(rec.created_at),
            "territory": study.territory if study else None, "phenomenon": study.phenomenon if study else None,
            "reserved": bool(study and study.access_level == "RESERVADO"),
            "summary": _short(rec.text),
            "outcome": ("Rechazada: " + (rec.decision_note or "sin motivo registrado")) if rejected else "Cumplida",
            "detail": {"addressed_to": rec.addressed_to, "study_code": study.code if study else None,
                       "commitment_code": rec.commitment_code, "decision_note": rec.decision_note,
                       "presented_on": rec.presented_on.isoformat() if rec.presented_on else None},
        })
    return items


def _evaluation_text(evaluation: Dict[str, Any]) -> str:
    before = (evaluation.get("before") or {}).get("value")
    after = (evaluation.get("after") or {}).get("value")
    if before is None or after is None:
        return "Evaluada"
    difference = evaluation.get("difference", after - before)
    sign = "+" if difference > 0 else ""
    return f"Evaluada: {int(before)} antes y {int(after)} después ({sign}{int(difference)}); no demuestra causalidad"


def intervention_items(db: Session) -> List[Dict[str, Any]]:
    items = []
    for case in db.query(InterventionCase).filter(InterventionCase.status.in_(("FINALIZADA", "EVALUADA"))).all():
        doc = case.document or {}
        evaluation = doc.get("evaluation")
        items.append({
            "kind": "INTERVENCION", "code": case.commitment_code or f"INT-{str(case.id)[:8]}",
            "title": _short(doc.get("intervention") or doc.get("problem"))[:200],
            "date": _day(doc.get("completed_on")) or _day(case.created_at),
            "territory": None, "phenomenon": doc.get("indicator"), "reserved": False,
            "summary": _short(doc.get("problem")),
            "outcome": _evaluation_text(evaluation) if evaluation else "Finalizada sin evaluar",
            "detail": {"decision": doc.get("decision"), "responsible": doc.get("responsible"),
                       "started_on": doc.get("started_on"), "completed_on": doc.get("completed_on"),
                       "assessment": (evaluation or {}).get("assessment"),
                       "evidence": [item.get("description") for item in doc.get("evidence") or []]},
        })
    return items


def _haystack(item: Dict[str, Any]) -> str:
    detail = item.get("detail") or {}
    parts = [item["code"], item["title"], item.get("territory"), item.get("phenomenon"), item["summary"], item["outcome"],
             detail.get("question"), detail.get("associated_factors"), detail.get("decision_note"), detail.get("assessment")]
    return fold(" ".join(str(part) for part in parts if part))


def build_memory(db: Session, include_reserved: bool, q: Optional[str] = None, kind: Optional[str] = None,
                 year: Optional[int] = None) -> Dict[str, Any]:
    items = study_items(db, include_reserved) + recommendation_items(db, include_reserved) + intervention_items(db)
    years = sorted({item["date"].year for item in items if item["date"]}, reverse=True)
    counts = {key: sum(1 for item in items if item["kind"] == key) for key in KINDS}
    if kind:
        items = [item for item in items if item["kind"] == kind]
    if year:
        items = [item for item in items if item["date"] and item["date"].year == year]
    if q:
        words = fold(q).split()
        items = [item for item in items if all(word in _haystack(item) for word in words)]
    items.sort(key=lambda item: (item["date"] or date.min, item["code"]), reverse=True)
    for item in items:
        item["date"] = item["date"].isoformat() if item["date"] else None
        item["kind_label"] = KINDS[item["kind"]]
    return {
        "items": items, "counts": counts, "years": years, "total": sum(counts.values()),
        "rule": ("Reúne estudios cerrados, recomendaciones rechazadas o cumplidas e intervenciones finalizadas o "
                 "evaluadas. Nada se reescribe: cada registro conserva lo que se decidió y por qué."),
    }


CSV_COLUMNS = ("Tipo", "Código", "Fecha", "Título", "Territorio", "Fenómeno", "Resultado", "Resumen")


def export_csv(memory: Dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(CSV_COLUMNS)
    for item in memory["items"]:
        writer.writerow([item["kind_label"], item["code"], item["date"] or "", item["title"], item.get("territory") or "",
                         item.get("phenomenon") or "", item["outcome"], item["summary"]])
    return "﻿" + buffer.getvalue()
