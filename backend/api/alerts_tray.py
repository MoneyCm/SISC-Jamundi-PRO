"""Bandeja operativa: revisión humana separada de la evidencia estadística."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import analyst_or_admin, institutional_access
from db.models import User, get_db
from db.models_alerts import AlertReview, IntelligenceAlert
from services.alert_rules import REVIEW_TRANSITIONS, review_alert

router = APIRouter()

REVIEW_ROLES_NOTE = "Lectura: nivel institucional. Revisar: analista o admin."


def _serialize(row: IntelligenceAlert) -> dict:
    return {
        "id": str(row.id),
        "indicator": (row.entity_ref or {}).get("indicator"),
        "territory": (row.entity_ref or {}).get("territory"),
        "tier": row.priority_tier,
        "severity": row.severity,
        "title": row.title,
        "reason": row.body_md,
        "status": row.status,
        "review_state": row.review_state,
        "review_version": row.review_version,
        "lineage_key": row.lineage_key,
        "previous_evaluation_id": str(row.previous_evaluation_id) if row.previous_evaluation_id else None,
        "superseded_by": str(row.superseded_by) if row.superseded_by else None,
        "supersede_note": row.supersede_note,
        "evidence": row.metrics,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/")
def list_tray(
    review_state: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    indicator: Optional[str] = Query(default=None),
    lineage_key: Optional[str] = Query(default=None),
    include_superseded: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(institutional_access),
):
    """Lista evaluaciones persistidas (la previsualización que calcula es GET /ia/alertas-semanales)."""
    q = db.query(IntelligenceAlert).filter(IntelligenceAlert.source == "SISC_WEEKLY")
    if review_state:
        q = q.filter(IntelligenceAlert.review_state == review_state.upper())
    if tier:
        q = q.filter(IntelligenceAlert.priority_tier == tier.upper())
    if indicator:
        q = q.filter(IntelligenceAlert.alert_type == f"WEEKLY_{indicator.upper()}")
    if lineage_key:
        q = q.filter(IntelligenceAlert.lineage_key == lineage_key)
    if not include_superseded:
        q = q.filter(IntelligenceAlert.status == "OPEN")
    rows = q.order_by(IntelligenceAlert.created_at.desc()).limit(limit).all()
    return {"items": [_serialize(r) for r in rows], "count": len(rows)}


@router.get("/{alert_id}")
def tray_detail(
    alert_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(institutional_access),
):
    row = db.query(IntelligenceAlert).filter(IntelligenceAlert.id == alert_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="No existe la alerta.")
    reviews = db.query(AlertReview).filter(AlertReview.alert_id == row.id).order_by(AlertReview.created_at.asc()).all()
    lineage = []
    if row.lineage_key:
        lineage = db.query(IntelligenceAlert).filter(
            IntelligenceAlert.lineage_key == row.lineage_key,
        ).order_by(IntelligenceAlert.created_at.asc()).all()
    return {
        "alert": _serialize(row),
        "reviews": [
            {"action": r.action, "prev_state": r.prev_state, "new_state": r.new_state,
             "username": r.username, "comment": r.comment,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in reviews
        ],
        "lineage": [{"id": str(r.id), "status": r.status, "review_state": r.review_state,
                     "tier": r.priority_tier, "created_at": r.created_at.isoformat() if r.created_at else None,
                     "supersede_note": r.supersede_note} for r in lineage],
        "transitions": sorted(REVIEW_TRANSITIONS.get(row.review_state or "PENDIENTE", set())),
    }


class ReviewRequest(BaseModel):
    action: str = Field(description="EN_ANALISIS | REVISADA | DESCARTADA | PENDIENTE")
    expected_version: int = Field(ge=0)
    comment: Optional[str] = None


@router.post("/{alert_id}/review")
def tray_review(
    alert_id: UUID,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(analyst_or_admin),
):
    """Registra la valoración (autor = sesión autenticada, fecha = servidor)."""
    return review_alert(
        db, alert_id=str(alert_id),
        username=current_user.username, user_id=str(current_user.id),
        action=payload.action, expected_version=payload.expected_version,
        comment=payload.comment,
    )
