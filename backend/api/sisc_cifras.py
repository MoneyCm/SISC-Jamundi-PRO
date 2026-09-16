import hashlib
import os
import secrets
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
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
    publish_automatically: bool = False
    source_version_id: Optional[UUID] = None


def _check_selected_delivery(db, payload, row=None):
    """A generator upload must never silently publish another delivery."""
    if not payload.source_version_id:
        return
    from services.publication_guards import require_fixed_delivery
    from services.indicator_calculation import _latest_completed_run
    require_fixed_delivery(db, str(payload.source_version_id))
    latest = _latest_completed_run(db)
    if not latest or str(latest.id) != str(payload.source_version_id):
        raise HTTPException(409, "Hay otra entrega vigente. Vuelva a cargar o seleccionar el archivo antes de publicar.")
    if row is not None:
        if str((row.source_version_ids or {}).get("POLICIA_SEMANAL")) != str(payload.source_version_id):
            raise HTTPException(409, "La entrega del boletín cambió durante el cálculo. Revise el borrador.")
        if row.period_start != payload.period_start or row.period_end != payload.period_end:
            raise HTTPException(422, "El corte disponible no cubre el período solicitado. Ajuste el período antes de publicar.")


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


@router.post("/generate", deprecated=True)
async def generate_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if payload.publish_automatically and not payload.save_history:
        raise HTTPException(status_code=422, detail="La publicacion automatica requiere guardar la version institucional.")
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

    _check_selected_delivery(db, payload)
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
    if payload.publish_automatically:
        publication_id = publication.get("id")
        row = db.query(SiscCifrasPublication).filter(
            SiscCifrasPublication.id == UUID(str(publication_id)),
        ).first() if publication_id else None
        if not row:
            raise HTTPException(status_code=500, detail="No fue posible recuperar el boletin generado.")
        from services.publication_guards import enforce_publication_integrity
        try:
            _check_selected_delivery(db, payload, row)
            integrity = enforce_publication_integrity(db, row)
        except Exception:
            db.rollback()
            raise
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
        governance["publication_note"] = "Publicacion automatica de informacion agregada y anonimizada; las alertas de cobertura se conservan como trazabilidad."
        governance["integrity"] = integrity
        snapshot["governance"] = governance
        snapshot["status"] = "PUBLISHED"
        snapshot["published_at"] = date.today().isoformat()
        snapshot["published_by"] = current_user.username
        row.status = "PUBLISHED"
        row.publication_json = snapshot
        db.commit()
        publication = snapshot
    if payload.save_history:
        await log_audit(
            db,
            "SISC_CIFRAS_PUBLISHED" if payload.publish_automatically else "SISC_CIFRAS_DRAFT_CREATED",
            actor_id=str(current_user.id),
            module="SISC_CIFRAS",
            target={
                "publication_id": publication.get("id"),
                "status": publication.get("status"),
                "period_start": str(payload.period_start) if payload.period_start else None,
                "period_end": str(payload.period_end) if payload.period_end else None,
            },
            level=1,
            request=request,
        )
    return publication


@router.post("/generate-pdf", deprecated=True)
def generate_sisc_cifras_pdf(
    payload: GenerateSiscCifrasRequest,
    db: Session = Depends(get_db),
):
    """DEPRECATED: Usar POST /v1/generate que incluye PDF atómico."""
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
    from services.sisc_cifras_pdf import build_sisc_cifras_pdf
    try:
        pdf_bytes = build_sisc_cifras_pdf(publication)
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": "inline; filename=boletin.pdf"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"PDF generation failed: {e}"})


@router.post("/publications/public/generate")
def generate_and_publish_public_sisc_cifras(
    payload: GenerateSiscCifrasRequest,
    x_publication_token: Optional[str] = Header(default=None, alias="X-Publication-Token"),
    db: Session = Depends(get_db),
):
    """Genera y publica datos agregados desde una aplicacion institucional confiable."""
    _require_automatic_publication_token(x_publication_token)
    _check_selected_delivery(db, payload)
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

    from services.publication_guards import enforce_publication_integrity
    try:
        _check_selected_delivery(db, payload, row)
        integrity = enforce_publication_integrity(db, row)
    except Exception:
        db.rollback()
        raise
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
    governance["integrity"] = integrity
    snapshot["governance"] = governance
    snapshot["status"] = "PUBLISHED"
    snapshot["published_at"] = date.today().isoformat()
    snapshot["published_by"] = "PLATAFORMA_SEGURIDAD"
    row.status = "PUBLISHED"
    row.publication_json = snapshot
    db.commit()
    return snapshot


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

    from services.publication_guards import enforce_publication_integrity
    try:
        integrity = enforce_publication_integrity(db, row)
    except Exception:
        db.rollback()
        raise
    governance["integrity"] = integrity
    publication["governance"] = governance
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
            "publication_json": row.publication_json,
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

    if row.pdf_data is not None:
        pdf_bytes = bytes(row.pdf_data)
        if row.pdf_sha256:
            actual_hash = hashlib.sha256(pdf_bytes).hexdigest()
            if actual_hash != row.pdf_sha256:
                pass
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

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


class IndicatorRequest(BaseModel):
    indicator: str = Field(default="HOMICIDIO")
    period: dict = Field(default={"start": "2026-01-01", "end": "2026-07-12"})
    territory: str = Field(default="JAMUNDI")
    source_version_id: Optional[str] = None
    methodology_version: str = Field(default="1")


class ReconcileRequest(BaseModel):
    publication_id: str
    new_source_version_id: str


@router.post("/indicator")
def calculate_single_indicator(
    payload: IndicatorRequest,
    db: Session = Depends(get_db),
):
    """Única función de cálculo oficial. Tablero, boletín, alertas y chat usan esta vía."""
    from services.indicator_calculation import calculate_indicator

    try:
        return calculate_indicator(
            db,
            indicator=payload.indicator,
            period_start=payload.period.get("start"),
            period_end=payload.period.get("end"),
            territory=payload.territory,
            source_version_id=payload.source_version_id,
            methodology_version=payload.methodology_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/indicators/catalog")
def get_indicator_catalog():
    from services.indicator_catalog import METHODOLOGY_VERSION, list_indicators

    return {"methodology_version": METHODOLOGY_VERSION, "indicators": list_indicators()}


@router.post("/reconcile")
def reconcile_publication_endpoint(
    payload: ReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    """Repite filtros y metodología de una publicación con una entrega nueva.

    Una actualización nunca sobrescribe: genera una nueva versión relacionada.
    """
    from services.reconciliation_service import reconcile_publication

    try:
        return reconcile_publication(db, payload.publication_id, payload.new_source_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class TriFuenteReconcileRequest(BaseModel):
    period_start: date
    period_end: date
    source_version_ids: dict


@router.post("/reconcile/tri-fuente/homicidios")
def reconcile_homicidios_tri_fuente_endpoint(
    payload: TriFuenteReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    """Conciliación tri-fuente de HOMICIDIOS: arbitraje forense, jamás suma capas.

    Exige las 3 entregas fijas (POLICIA_SEMANAL, FISCALIA_SPOA_V3,
    MEDICINA_LEGAL); si falta alguna responde 422 y la publicación queda
    bloqueada. |Δ|>1 en algún par marca WARNING con evidencia, nunca bloquea.
    """
    from services.reconciliation_tri_fuente_service import reconcile_homicidios_tri_fuente

    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="La fecha inicial debe ser anterior al corte.")
    try:
        return reconcile_homicidios_tri_fuente(
            db,
            period_start=payload.period_start,
            period_end=payload.period_end,
            source_version_ids=payload.source_version_ids or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class LegacyImportRequest(BaseModel):
    period_start: date
    period_end: date
    edition_type: str = Field(default="weekly")
    total_semana: Optional[int] = None
    total_ytd: Optional[int] = None
    totales_por_conducta_ytd: Optional[dict] = None
    nombre_archivo: Optional[str] = None
    hash_archivo: Optional[str] = None
    source_version_id: Optional[str] = None
    methodology_version: Optional[str] = None
    motivo: Optional[str] = "importacion_historial_navegador"


@router.post("/publications/import-legacy")
async def import_legacy_bulletin(
    payload: LegacyImportRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(PUBLICATION_ROLES)),
):
    """Importa boletines del historial del navegador distinguiendo:

    - REPRODUCIBLE: la entrega existe y es utilizable, los filtros/unidad están
      completos, la metodología es ejecutable y el recálculo coincide con lo importado.
    - CIFRAS_DECLARADAS: conserva lo publicado con su razón, sin conciliación
      detallada de registros.
    """
    from uuid import UUID, uuid4
    from db.models_hechos_seguridad import IngestionRun
    from services.indicator_calculation import calculate_indicator
    from services.indicator_catalog import METHODOLOGY_VERSION, get_indicator_meta

    reasons: list[str] = []
    run = None
    if payload.source_version_id:
        try:
            run = db.query(IngestionRun).filter(
                IngestionRun.id == UUID(str(payload.source_version_id)),
                IngestionRun.fuente_codigo == "POLICIA_SEMANAL",
            ).first()
        except ValueError:
            run = None
        if not run:
            reasons.append("la entrega indicada no existe en el servidor")
        elif run.status != "COMPLETED":
            reasons.append(f"la entrega existe pero su estado es {run.status}, no utilizable")
    else:
        reasons.append("sin source_version_id verificable")
    if not payload.methodology_version:
        reasons.append("sin methodology_version")
    elif payload.methodology_version != METHODOLOGY_VERSION:
        raise HTTPException(status_code=422, detail=f"methodology_version={payload.methodology_version} no ejecutable en este backend.")
    if payload.total_ytd is None:
        reasons.append("sin total YTD declarado para comprobar")
    try:
        meta = get_indicator_meta("SEGURIDAD_TOTAL")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    reproducible = False
    recalculated = None
    if run is not None and run.status == "COMPLETED" and payload.methodology_version == METHODOLOGY_VERSION and payload.total_ytd is not None:
        try:
            recalculated = calculate_indicator(
                db, indicator="SEGURIDAD_TOTAL",
                period_start=payload.period_start, period_end=payload.period_end,
                territory="JAMUNDI", source_version_id=str(run.id),
                methodology_version=METHODOLOGY_VERSION,
            )
            if int(recalculated["value"]) != int(payload.total_ytd):
                reasons.append(f"el recálculo ({recalculated['value']}) no coincide con lo declarado ({payload.total_ytd})")
            else:
                reproducible = True
        except Exception as exc:
            reasons.append(f"no se pudo recalcular: {exc}")

    if not reproducible and not reasons:
        reasons.append("verificación incompleta")
    # Protección contra importaciones duplicadas: mismo periodo + misma huella de archivo.
    if payload.hash_archivo:
        dup = db.query(SiscCifrasPublication).filter(
            SiscCifrasPublication.period_start == payload.period_start,
            SiscCifrasPublication.period_end == payload.period_end,
            SiscCifrasPublication.publication_json.op("->")("governance").op("->>")("origin") == payload.motivo,
        ).all()
        for row in dup:
            prov = ((row.publication_json or {}).get("governance") or {}).get("provenance") or {}
            if prov.get("hash_archivo") == payload.hash_archivo:
                raise HTTPException(status_code=409, detail="Ese historial ya fue importado (misma huella de archivo y periodo).")
    pub_id = uuid4()
    publication = {
        "id": str(pub_id),
        "title": "SISC EN CIFRAS",
        "edition_type": payload.edition_type,
        "period": {"start": payload.period_start.isoformat(), "end": payload.period_end.isoformat()},
        "comparison_period": {"start": "", "end": ""},
        "comparison_label": "",
        "comparison_mode": "year_over_year",
        "status": "PUBLISHED",
        "generated_at": date.today().isoformat(),
        "sources": [],
        "indicators": [],
        "governance": {
            "public_only": True,
            "human_review_required": False,
            "imported_legacy": True,
            "reproducible": reproducible,
            "reproducibility": "REPRODUCIBLE" if reproducible else "CIFRAS_DECLARADAS",
            "reproducibility_reasons": reasons if not reproducible else [],
            "recalculated_check": recalculated,
            "unit": meta["unit_label"],
            "origin": payload.motivo,
            "provenance": {"nombre_archivo": payload.nombre_archivo, "hash_archivo": payload.hash_archivo},
        },
        "legacy_totals": {
            "total_semana": payload.total_semana,
            "total_ytd": payload.total_ytd,
            "totales_por_conducta_ytd": payload.totales_por_conducta_ytd or {},
        },
    }
    row = SiscCifrasPublication(
        id=pub_id,
        title="SISC EN CIFRAS",
        edition_type=payload.edition_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        created_by=current_user.username,
        source_codes=["POLICIA_SEMANAL"],
        publication_json=publication,
        methodology_version=payload.methodology_version,
        source_version_ids={"POLICIA_SEMANAL": payload.source_version_id} if payload.source_version_id else None,
    )
    db.add(row)
    db.commit()
    await log_audit(
        db, "SISC_CIFRAS_LEGACY_IMPORTED", actor_id=str(current_user.id), module="SISC_CIFRAS",
        target={"publication_id": str(pub_id), "reproducible": reproducible}, level=2, request=request,
    )
    return {"id": str(pub_id), "reproducibility": publication["governance"]["reproducibility"]}
