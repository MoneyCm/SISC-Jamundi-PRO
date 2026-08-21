"""
SISC Cifras API v1 — Contrato aprobado con BulletinFilters.
Endpoints versionados bajo /api/sisc-cifras/v1/.
"""

import hashlib
import time
import base64
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from db.session import get_db
from db.models_sisc_cifras import SiscCifrasPublication
from schemas.bulletin_filters import BulletinFilters
from schemas.bulletin_responses import (
    CapabilitiesResponse,
    CatalogResponse,
    GenerateResponse,
    ExploreResponse,
    SiscErrorResponse,
    PublicationSnapshot,
)
from services.sisc_cifras_service import SiscCifrasService
from services.sisc_cifras_pdf import build_sisc_cifras_pdf
from middleware.rate_limit import rate_limit_explore
from api.auth import get_optional_user

router = APIRouter(prefix="/v1", tags=["sisc-cifras-v1"])

PUBLICATION_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]
ANALYSIS_ROLES = ["ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"]


def _resolve_filters(filters: BulletinFilters, db: Session) -> dict:
    start = filters.period.start
    end = filters.period.end
    days = (end - start).days + 1
    today = date.today()
    tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())

    comp_start, comp_end = None, None
    if filters.comparison.mode == "YEAR_OVER_YEAR":
        comp_start = date(start.year - 1, start.month, start.day)
        comp_end = date(end.year - 1, end.month, end.day)
    elif filters.comparison.mode == "PREVIOUS_PERIOD":
        period_len = (end - start).days
        comp_end = start - timedelta(days=1)
        comp_start = comp_end - timedelta(days=period_len)

    resolved_barrios = ["TODO_JAMUNDI"]
    if filters.territory.scope == "BARRIO" and filters.territory.selected_codes:
        resolved_barrios = filters.territory.selected_codes
    elif filters.territory.scope == "COMUNA":
        resolved_barrios = filters.territory.selected_codes

    records = SiscCifrasService.collect_dataset_identity(db, start, end)

    return {
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": filters.period.timezone,
            "days": days,
        },
        "comparison": {
            "mode": filters.comparison.mode,
            "resolved_by_backend": comp_start is not None,
            "start": comp_start.isoformat() if comp_start else None,
            "end": comp_end.isoformat() if comp_end else None,
        },
        "sources": {
            "active": filters.sources,
            "cutoff_used": end.isoformat(),
            "records": {
                code: {
                    "cutoff_date": records.get(code, {}).get("cutoff_date"),
                    "unique_count": records.get(code, {}).get("unique_count", 0),
                    "content_hash": records.get(code, {}).get("content_hash"),
                }
                for code in filters.sources
            },
        },
        "territory": {
            "scope": filters.territory.scope,
            "zona": filters.territory.zona,
            "resolved_barrios": resolved_barrios,
        },
        "conductas": {
            "mode": filters.conductas.mode,
            "resolved_codes": filters.conductas.selected_codes,
        },
    }


def _dataset_identity_from_resolved(resolved: dict) -> dict:
    records = resolved.get("sources", {}).get("records", {})
    return {code: info for code, info in records.items() if isinstance(info, dict)}


def _infer_bulletin_type_from_period(start, end):
    """Infer bulletin_type from period duration when not explicitly set."""
    days = (end - start).days + 1
    if days <= 8:
        return "WEEKLY"
    elif days <= 32:
        return "MONTHLY"
    else:
        return "ANNUAL"


# --- GET /v1/capabilities ---

@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_capabilities():
    return SiscCifrasService.get_capabilities()


# --- GET /v1/catalogs/{catalog_name} ---

@router.get("/catalogs/{catalog_name}", response_model=CatalogResponse)
def get_catalog(catalog_name: str):
    valid = {"conductas", "presets", "barrios", "territorios"}
    if catalog_name not in valid:
        raise HTTPException(404, f"Catálogo '{catalog_name}' no encontrado. Válidos: {valid}")
    result = SiscCifrasService.get_catalog(catalog_name)
    if result.get("status") == "error":
        raise HTTPException(404, result.get("message", "Catálogo no encontrado"))
    return result


# --- POST /v1/generate ---

@router.post("/generate", response_model=GenerateResponse)
def generate_v1(
    filters: BulletinFilters,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
):
    if not user:
        raise HTTPException(401, "Autenticación requerida para generar boletines.")
    user_role_codes = [r.code for r in (user.roles or [])]
    if "TI_ADMIN" not in user_role_codes:
        has_role = any(role in user_role_codes for role in PUBLICATION_ROLES)
        if not has_role:
            raise HTTPException(403, "No tiene permiso para generar boletines.")
    if filters.mode != "OFFICIAL_PUBLICATION":
        raise HTTPException(400, "Este endpoint solo acepta mode=OFFICIAL_PUBLICATION.")

    filters_dict = filters.model_dump(mode="json")
    resolved = _resolve_filters(filters, db)

    catalog_versions = SiscCifrasService._load_catalog_versions()
    dataset_id = _dataset_identity_from_resolved(resolved)
    query_hash = SiscCifrasService.generate_query_hash(
        filters_dict, resolved, catalog_versions, dataset_id,
    )

    existing = SiscCifrasService.find_existing_by_query_hash(db, query_hash)
    if existing:
        snapshot = SiscCifrasService.adapt_legacy_publication(existing)
        return GenerateResponse(
            schema_version="1.0",
            status="ok",
            mode=filters.mode,
            bulletin_type=filters.bulletin_type,
            snapshot=PublicationSnapshot(**snapshot),
            created_at=existing.created_at or datetime.utcnow(),
        )

    try:
        publication = SiscCifrasService.generate_publication(
            db,
            edition_type=filters.bulletin_type.lower().replace("_special", ""),
            period_start=filters.period.start,
            period_end=filters.period.end,
            comparison_mode=filters.comparison.mode.lower(),
            source_codes=filters.sources,
            max_insights=5,
            created_by=str(user.id) if hasattr(user, "id") else "system",
            save_history=False,
        )
    except Exception as e:
        raise HTTPException(500, detail=f"Error generando publicación: {e}")

    suppressed_cells = []
    for ind in publication.get("indicators", []):
        count = int(ind.get("value", 0))
        if count < 5:
            suppressed_cells.append({
                "cell_id": f"{ind.get('source_code', '')}:{ind.get('indicator_code', '')}",
                "reason": "MINIMUM_CELL_SIZE",
                "source": ind.get("source_code", ""),
                "row_label": ind.get("indicator_name", ""),
                "column_label": "current",
                "threshold_used": 5,
            })

    pdf_url = f"/api/sisc-cifras/publications/{publication.get('id')}/pdf"
    snapshot = SiscCifrasService.build_snapshot_from_publication(
        publication, filters_dict, resolved, catalog_versions,
        suppressed_cells, str(user.id), pdf_url,
    )

    try:
        pdf_bytes = build_sisc_cifras_pdf(publication)
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    except Exception:
        db.rollback()
        raise HTTPException(500, detail="Error generando PDF.")

    publication_id = publication.get("id")
    row = SiscCifrasPublication(
        id=publication_id,
        title=publication.get("title", "SISC EN CIFRAS"),
        edition_type=filters.bulletin_type,
        period_start=filters.period.start,
        period_end=filters.period.end,
        status="PUBLISHED",
        created_by=str(user.id) if hasattr(user, "id") else "system",
        source_codes=filters.sources,
        publication_json=publication,
        requested_filters=filters_dict,
        resolved_filters=resolved,
        schema_version="1.0",
        pdf_url=pdf_url,
        pdf_data=pdf_bytes,
        pdf_sha256=pdf_sha256,
        hash_integrity=snapshot["hash_integrity"],
        suppressed_cells=suppressed_cells,
        catalog_versions_used=catalog_versions,
        query_hash=query_hash,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(500, detail="Error guardando publicación.")

    return GenerateResponse(
        schema_version="1.0",
        status="ok",
        mode=filters.mode,
        bulletin_type=filters.bulletin_type,
        snapshot=PublicationSnapshot(**snapshot),
        created_at=datetime.utcnow(),
    )


# --- POST /v1/explore ---

@router.post("/explore", response_model=ExploreResponse)
def explore_v1(
    filters: BulletinFilters,
    request: Request,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_explore),
):
    if filters.mode != "PUBLIC_EXPLORATION":
        raise HTTPException(400, "Este endpoint solo acepta mode=PUBLIC_EXPLORATION.")

    start_time = time.time()
    filters_dict = filters.model_dump(mode="json")
    resolved = _resolve_filters(filters, db)

    try:
        if filters.bulletin_type:
            edition_type = filters.bulletin_type.lower().replace("_special", "")
        else:
            edition_type = _infer_bulletin_type_from_period(filters.period.start, filters.period.end).lower()
        result_data = SiscCifrasService.query_explore_data(
            db,
            edition_type=edition_type,
            period_start=filters.period.start,
            period_end=filters.period.end,
            comparison_mode=filters.comparison.mode.lower(),
            source_codes=filters.sources,
            territory_scope=filters.territory.scope,
            territory_codes=filters.territory.selected_codes,
            conducta_mode=filters.conductas.mode,
            conducta_codes=filters.conductas.selected_codes,
        )
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    indicators = result_data.get("indicators", [])
    domain_map = {
        "POLICIA_SEMANAL": ("HECHOS_DELICTIVOS", "HECHOS"),
        "INSPECCIONES_RNMC": ("ACTUACIONES_INSPECCION", "ACTUACIONES"),
        "COMISARIAS_FAMILIA": ("ATENCIONES_COMISARIA", "ATENCIONES"),
    }

    results = []
    suppressed_cells = []
    warnings = []
    for ind in indicators:
        source_code = ind.source_code
        if source_code not in domain_map:
            continue
        domain, unit = domain_map[source_code]
        count = int(ind.value)
        comparison_count = int(ind.comparison_value) if ind.comparison_value is not None else None
        is_suppressed = count < 5
        result = {
            "key": ind.indicator_code,
            "label": ind.indicator_name,
            "domain": domain,
            "source_code": source_code,
            "unit": unit,
            "is_suppressed": is_suppressed,
            "count": None if is_suppressed else count,
            "comparison_count": None if is_suppressed else comparison_count,
            "percentage_change": None if is_suppressed else ind.variation_percentage,
        }
        if is_suppressed:
            result["suppression_reason"] = "MINIMUM_CELL_SIZE"
            suppressed_cells.append({
                "cell_id": f"{source_code}:{ind.indicator_code}",
                "reason": "MINIMUM_CELL_SIZE",
                "source": source_code,
                "row_label": ind.indicator_name,
                "column_label": "current",
                "threshold_used": 5,
            })
        results.append(result)

    if any(r["is_suppressed"] for r in results):
        warnings.append({
            "code": "SMALL_SAMPLE_SIZE",
            "message": "Algunos resultados fueron suprimidos por protección estadística (count < 5).",
            "severity": "warning",
        })

    query_time_ms = int((time.time() - start_time) * 1000)

    return ExploreResponse(
        schema_version="1.0",
        status="partial" if suppressed_cells else "ok",
        results=results,
        total_results=len(results),
        resolved_filters=resolved,
        warnings=warnings,
        suppressed_cells=suppressed_cells,
        metadata={
            "query_time_ms": query_time_ms,
            "data_sources_queried": filters.sources,
            "filters_applied": sum(1 for v in filters_dict.values() if v),
        },
    )


# --- POST /v1/analyze ---

@router.post("/analyze", response_model=ExploreResponse)
def analyze_v1(
    filters: BulletinFilters,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
):
    if filters.mode != "INSTITUTIONAL_ANALYSIS":
        raise HTTPException(400, "Este endpoint solo acepta mode=INSTITUTIONAL_ANALYSIS.")
    if not user:
        raise HTTPException(401, "Autenticación requerida para análisis institucional.")
    user_role_codes = [r.code for r in (user.roles or [])]
    if "TI_ADMIN" not in user_role_codes:
        has_role = any(role in user_role_codes for role in ANALYSIS_ROLES)
        if not has_role:
            raise HTTPException(403, "No tiene permiso para análisis institucional.")

    start_time = time.time()
    filters_dict = filters.model_dump(mode="json")
    resolved = _resolve_filters(filters, db)

    try:
        if filters.bulletin_type:
            edition_type = filters.bulletin_type.lower().replace("_special", "")
        else:
            edition_type = _infer_bulletin_type_from_period(filters.period.start, filters.period.end).lower()
        result_data = SiscCifrasService.query_explore_data(
            db,
            edition_type=edition_type,
            period_start=filters.period.start,
            period_end=filters.period.end,
            comparison_mode=filters.comparison.mode.lower(),
            source_codes=filters.sources,
            territory_scope=filters.territory.scope,
            territory_codes=filters.territory.selected_codes,
            conducta_mode=filters.conductas.mode,
            conducta_codes=filters.conductas.selected_codes,
        )
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    indicators = result_data.get("indicators", [])
    domain_map = {
        "POLICIA_SEMANAL": ("HECHOS_DELICTIVOS", "HECHOS"),
        "INSPECCIONES_RNMC": ("ACTUACIONES_INSPECCION", "ACTUACIONES"),
        "COMISARIAS_FAMILIA": ("ATENCIONES_COMISARIA", "ATENCIONES"),
    }

    results = []
    suppressed_cells = []
    warnings = []
    for ind in indicators:
        source_code = ind.source_code
        if source_code not in domain_map:
            continue
        domain, unit = domain_map[source_code]
        count = int(ind.value)
        comparison_count = int(ind.comparison_value) if ind.comparison_value is not None else None
        is_suppressed = count < 5
        result = {
            "key": ind.indicator_code,
            "label": ind.indicator_name,
            "domain": domain,
            "source_code": source_code,
            "unit": unit,
            "is_suppressed": is_suppressed,
            "count": None if is_suppressed else count,
            "comparison_count": None if is_suppressed else comparison_count,
            "percentage_change": None if is_suppressed else ind.variation_percentage,
        }
        if is_suppressed:
            result["suppression_reason"] = "MINIMUM_CELL_SIZE"
            suppressed_cells.append({
                "cell_id": f"{source_code}:{ind.indicator_code}",
                "reason": "MINIMUM_CELL_SIZE",
                "source": source_code,
                "row_label": ind.indicator_name,
                "column_label": "current",
                "threshold_used": 5,
            })
        results.append(result)

    if any(r["is_suppressed"] for r in results):
        warnings.append({
            "code": "SMALL_SAMPLE_SIZE",
            "message": "Algunos resultados fueron suprimidos por protección estadística (count < 5).",
            "severity": "warning",
        })

    query_time_ms = int((time.time() - start_time) * 1000)

    return ExploreResponse(
        schema_version="1.0",
        status="partial" if suppressed_cells else "ok",
        results=results,
        total_results=len(results),
        resolved_filters=resolved,
        warnings=warnings,
        suppressed_cells=suppressed_cells,
        metadata={
            "query_time_ms": query_time_ms,
            "data_sources_queried": filters.sources,
            "filters_applied": sum(1 for v in filters_dict.values() if v),
        },
    )
