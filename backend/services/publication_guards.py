"""Guardas de publicación: el botón deshabilitado no basta, el backend rechaza.

Una publicación exige:
- entrega fija (source_version_id) existente y COMPLETED por cada fuente de hechos;
- metodología válida y ejecutable;
- filtros consistentes (periodo válido, territorio soportado);
- cifras calculadas o verificadas en el servidor (no acepta cifras locales).

Toda cifra oficial verificada expone indicador, unidad, período, entrega y metodología.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db.models_hechos_seguridad import IngestionRun
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import METHODOLOGY_VERSION


def _ensure_uuid(value: str, name: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{name} debe ser UUID.")


def require_fixed_delivery(db: Session, source_version_id: Optional[str], *, source: str = "POLICIA_SEMANAL") -> IngestionRun:
    if not source_version_id:
        raise HTTPException(status_code=422, detail=f"Publicar exige entrega fija ({source}): source_version_id ausente. La exploración sobre consolidado vigente no es publicable.")
    run = db.query(IngestionRun).filter(
        IngestionRun.id == _ensure_uuid(source_version_id, "source_version_id"),
        IngestionRun.fuente_codigo == source,
    ).first()
    if not run:
        raise HTTPException(status_code=422, detail=f"La entrega {source_version_id} no existe en el servidor.")
    if run.status != "COMPLETED":
        raise HTTPException(status_code=422, detail=f"La entrega {source_version_id} no es utilizable (estado {run.status}).")
    return run


def require_methodology(version: Optional[str]) -> str:
    if not version:
        raise HTTPException(status_code=422, detail="Publicar exige methodology_version explícita.")
    if version != METHODOLOGY_VERSION:
        raise HTTPException(status_code=422, detail=f"methodology_version={version} no ejecutable. Vigente: {METHODOLOGY_VERSION}.")
    return version


def require_period(start: date, end: date, *, max_days: int = 366) -> None:
    if start > end:
        raise HTTPException(status_code=422, detail="La fecha inicial no puede ser posterior al corte.")
    if (end - start).days > max_days:
        raise HTTPException(status_code=422, detail=f"El periodo no puede superar {max_days + 1} días.")


def verify_official_figures(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    source_version_id: str,
    methodology_version: str,
    expected: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Recalcula en el servidor y, si se aportan cifras, exige coincidencia exacta.

    `expected`: {SEGURIDAD_TOTAL: n, HOMICIDIO: m}. Si es None, solo devuelve lo calculado.
    """
    out: Dict[str, Any] = {}
    for code in ("SEGURIDAD_TOTAL", "HOMICIDIO"):
        try:
            out[code] = calculate_indicator(
                db, indicator=code, period_start=period_start, period_end=period_end,
                territory="JAMUNDI", source_version_id=source_version_id,
                methodology_version=methodology_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    if expected:
        for code, want in expected.items():
            if want is None:
                continue
            got = out.get(code, {}).get("value")
            if got is None or int(got) != int(want):
                raise HTTPException(
                    status_code=422,
                    detail=f"La cifra {code} no coincide con el servidor (declarado {want}, servidor {got}). No se publica cálculo local.",
                )
    return out


TRI_FUENTE_SOURCES = ("POLICIA_SEMANAL", "FISCALIA_SPOA_V3", "MEDICINA_LEGAL")


def require_tri_fuente_homicidios(db: Session, row) -> Dict[str, Any]:
    """Exige las 3 entregas fijas y adjunta la conciliación tri-fuente.

    Solo actúa cuando la publicación declara capa SPOA o INMLCF (es decir,
    opta al arbitraje tri-fuente de homicidios). Si falta alguna entrega
    responde 422 y la publicación queda bloqueada; |Δ|>1 marca WARNING con
    evidencia pero no bloquea. El resultado se devuelve para guardarlo en
    `governance.integrity.tri_fuente_homicidios`.
    """
    from services.reconciliation_tri_fuente_service import reconcile_homicidios_tri_fuente

    versions = dict(getattr(row, "source_version_ids", None) or {})
    codes = set(getattr(row, "source_codes", None) or []) | set(versions.keys())
    if not ({"FISCALIA_SPOA_V3", "MEDICINA_LEGAL"} & codes):
        return {}
    missing = [code for code in TRI_FUENTE_SOURCES if not versions.get(code)]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Publicar homicidios con arbitraje tri-fuente exige entrega fija de: {', '.join(missing)}.",
        )
    try:
        result = reconcile_homicidios_tri_fuente(
            db,
            period_start=row.period_start,
            period_end=row.period_end,
            source_version_ids=versions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return result


def enforce_publication_integrity(db: Session, row) -> Dict[str, Any]:
    """Exige entrega fija + metodología + cifras verificadas antes de publicar.

    Llamar después de crear la fila y antes de marcar PUBLISHED. Revierte con 422 si falta.
    """
    from db.models_sisc_cifras import SiscCifrasPublication  # noqa: F401 (tipo dinámico)

    methodology = getattr(row, "methodology_version", None)
    require_methodology(methodology)
    require_period(row.period_start, row.period_end)
    versions = dict(getattr(row, "source_version_ids", None) or {})
    if "POLICIA_SEMANAL" in (getattr(row, "source_codes", None) or []) and not versions.get("POLICIA_SEMANAL"):
        raise HTTPException(status_code=422, detail="Publicar exige entrega fija de POLICIA_SEMANAL (source_version_id).")
    delivery = versions.get("POLICIA_SEMANAL")
    verified: Dict[str, Any] = {}
    if delivery:
        require_fixed_delivery(db, delivery)
        verified = verify_official_figures(
            db, period_start=row.period_start, period_end=row.period_end,
            source_version_id=delivery, methodology_version=methodology,
        )
        pub = dict(getattr(row, "publication_json", None) or {})
        by_code = {i.get("indicator_code"): i for i in pub.get("indicators", [])}
        total_pub = (by_code.get("seguridad.total") or {}).get("value")
        if total_pub is not None and int(total_pub) != int(verified["SEGURIDAD_TOTAL"]["value"]):
            raise HTTPException(
                status_code=422,
                detail=f"La publicación no coincide con el servidor (boletín {total_pub}, servidor {verified['SEGURIDAD_TOTAL']['value']}).",
            )
    tri_fuente = require_tri_fuente_homicidios(db, row)
    return {
        "source_version_ids": versions,
        "methodology_version": methodology,
        "verified": verified,
        "tri_fuente_homicidios": tri_fuente,
    }
