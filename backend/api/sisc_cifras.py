import os
import secrets
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import get_optional_user, log_audit, require_role
from db.models import User
from db.models_sisc_cifras import SiscCifrasPublication
from db.session import get_db
from services.sisc_cifras_service import SiscCifrasService
from services.sisc_cifras_pdf import build_sisc_cifras_pdf

router = APIRouter()
PUBLICATION_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]
PUBLIC_SOURCE_CODES = ["POLICIA_SEMANAL", "INSPECCIONES_RNMC", "COMISARIAS_FAMILIA"]


class GenerateSiscCifrasRequest(BaseModel):
    edition_type: str = Field(default="weekly")
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    comparison_mode: str = Field(default="auto")
    source_codes: Optional[List[str]] = None
    max_insights: int = Field(default=5, ge=3, le=6)
    save_history: bool = False


def _can_save_publication(user: Optional[User]) -> bool:
    if user is None:
        return False
    role_codes = {role.code for role in (user.roles or [])}
    return bool(role_codes.intersection(PUBLICATION_ROLES))


def _require_automatic_publication_token(token: Optional[str]) -> None:
    expected = os.getenv("SISC_AUTO_PUBLICATION_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La publicacion automatica no esta configurada en el servidor.",
        )
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La plataforma solicitante no esta autorizada para publicar.",
        )


@router.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
):
    return SiscCifrasService.source_registry(db)


@router.get("/operational-summary")
def get_operational_summary(
    period_start: date = Query(...),
    period_end: date = Query(...),
    comparison_mode: str = Query(default="previous_year"),
    db: Session = Depends(get_db),
):
    if period_start > period_end:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior al corte.")
    if (period_end - period_start).days > 366:
        raise HTTPException(status_code=422, detail="El periodo no puede superar 367 dias.")
    if comparison_mode not in {"previous_year", "previous_period"}:
        raise HTTPException(status_code=422, detail="El comparativo solicitado no es valido.")

    return SiscCifrasService.operational_summary(
        db,
        period_start=period_start,
        period_end=period_end,
        comparison_mode=comparison_mode,
    )


@router.post("/generate")
async def generate_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if payload.save_history and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debe iniciar sesion para guardar un borrador institucional.",
        )
    if payload.save_history and not _can_save_publication(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su rol no permite guardar publicaciones institucionales.",
        )

    publication = SiscCifrasService.generate_publication(
        db,
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        comparison_mode=payload.comparison_mode,
        source_codes=payload.source_codes,
        max_insights=payload.max_insights,
        created_by=current_user.username if current_user else None,
        save_history=payload.save_history,
    )
    if payload.save_history:
        await log_audit(
            db,
            "SISC_CIFRAS_DRAFT_CREATED",
            actor_id=str(current_user.id),
            module="SISC_CIFRAS",
            target={
                "publication_id": publication.get("id"),
                "period_start": str(payload.period_start) if payload.period_start else None,
                "period_end": str(payload.period_end) if payload.period_end else None,
            },
            level=1,
            request=request,
        )
    return publication


@router.post("/generate-pdf")
def generate_sisc_cifras_pdf(
    payload: GenerateSiscCifrasRequest,
    db: Session = Depends(get_db),
):
    publication = SiscCifrasService.generate_publication(
        db,
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        comparison_mode=payload.comparison_mode,
        source_codes=payload.source_codes,
        max_insights=payload.max_insights,
        save_history=False,
    )


@router.post("/publications/public/generate")
def generate_and_publish_public_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    x_publication_token: Optional[str] = Header(default=None, alias="X-Publication-Token"),
    db: Session = Depends(get_db),
):
    """Genera y publica datos agregados desde una aplicacion institucional confiable."""
    _require_automatic_publication_token(x_publication_token)
    selected_sources = [
        code for code in (payload.source_codes or PUBLIC_SOURCE_CODES)
        if code in PUBLIC_SOURCE_CODES
    ]
    if not selected_sources:
        raise HTTPException(status_code=422, detail="No se seleccionaron fuentes publicables.")

    publication = SiscCifrasService.generate_publication(
        db,
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        comparison_mode=payload.comparison_mode,
        source_codes=selected_sources,
        max_insights=payload.max_insights,
        created_by="PLATAFORMA_SEGURIDAD",
        save_history=True,
    )
    publication_id = publication.get("id")
    if not publication_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible guardar el boletin en el repositorio central.",
        )

    row = db.query(SiscCifrasPublication).filter(
        SiscCifrasPublication.id == UUID(str(publication_id)),
    ).first()
    if not row:
        raise HTTPException(status_code=500, detail="El boletin generado no pudo recuperarse.")

    previous_rows = db.query(SiscCifrasPublication).filter(
        SiscCifrasPublication.id != row.id,
        SiscCifrasPublication.edition_type == row.edition_type,
        SiscCifrasPublication.period_start == row.period_start,
        SiscCifrasPublication.period_end == row.period_end,
        SiscCifrasPublication.status == "PUBLISHED",
    ).all()
    for previous in previous_rows:
        previous.status = "SUPERSEDED"
        previous_snapshot = dict(previous.publication_json or {})
        previous_snapshot["status"] = "SUPERSEDED"
        previous.publication_json = previous_snapshot

    snapshot = dict(publication)
    governance = dict(snapshot.get("governance") or {})
    governance["human_review_required"] = False
    governance["automatic_publication"] = True
    governance["publication_note"] = (
        "Publicacion automatica de indicadores agregados y anonimizados; "
        "las advertencias de cobertura se conservan para su correcta interpretacion."
    )
    snapshot["governance"] = governance
    snapshot["status"] = "PUBLISHED"
    snapshot["published_at"] = date.today().isoformat()
    snapshot["published_by"] = "PLATAFORMA_SEGURIDAD"
    row.status = "PUBLISHED"
    row.publication_json = snapshot
    db.commit()
    return snapshot
    period = publication.get("period") or {}
    filename = f"SISC_en_Cifras_{period.get('start', 'periodo')}_{period.get('end', 'corte')}.pdf"
    return Response(
        content=build_sisc_cifras_pdf(publication),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/publications/{publication_id}/approve")
async def approve_sisc_cifras_publication(
    publication_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    row = db.query(SiscCifrasPublication).filter(SiscCifrasPublication.id == publication_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="No existe el boletin solicitado.")

    publication = dict(row.publication_json or {})
    governance = publication.get("governance") or {}
    if not governance.get("publication_ready"):
        raise HTTPException(
            status_code=422,
            detail="El boletin no puede publicarse hasta resolver las observaciones de cobertura y calidad.",
        )

    row.status = "PUBLISHED"
    publication["status"] = "PUBLISHED"
    publication["published_at"] = date.today().isoformat()
    publication["published_by"] = current_user.username
    row.publication_json = publication
    db.commit()

    await log_audit(
        db,
        "SISC_CIFRAS_PUBLISHED",
        actor_id=str(current_user.id),
        module="SISC_CIFRAS",
        target={"publication_id": str(row.id), "period_end": row.period_end.isoformat()},
        level=1,
        request=request,
    )
    return {"id": str(row.id), "status": row.status, "published_at": publication["published_at"]}


@router.get("/publications/public")
def list_public_sisc_cifras_publications(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = db.query(SiscCifrasPublication).filter(
        SiscCifrasPublication.status == "PUBLISHED",
    ).order_by(SiscCifrasPublication.period_end.desc(), SiscCifrasPublication.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "edition_type": row.edition_type,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "published_at": (row.publication_json or {}).get("published_at"),
            "source_codes": row.source_codes,
        }
        for row in rows
    ]


@router.get("/publications/{publication_id}/pdf")
def get_public_sisc_cifras_pdf(
    publication_id: UUID,
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    row = db.query(SiscCifrasPublication).filter(
        SiscCifrasPublication.id == publication_id,
        SiscCifrasPublication.status == "PUBLISHED",
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="El boletin no esta disponible para consulta publica.")

    filename = f"SISC_en_Cifras_{row.period_start.isoformat()}_{row.period_end.isoformat()}.pdf"
    disposition = "attachment" if download else "inline"
    return Response(
        content=build_sisc_cifras_pdf(row.publication_json or {}),
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/publications")
def list_publications(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    return SiscCifrasService.list_publications(db, limit=limit)
