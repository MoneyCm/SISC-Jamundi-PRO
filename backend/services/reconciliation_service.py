"""Conciliación histórica backend — mismos filtros y metodología, solo cambia la versión de datos.

Publicado con entrega A: 54
Recalculado con entrega B: 55
Diferencia: +1

Separa dos preguntas:
1. ¿Qué cambió en los registros? (altas, modificaciones, reclasificaciones, ausentes)
2. ¿Cómo afectó a cada indicador publicado?

- Ausente en una entrega NO significa eliminado: depende de sábana completa vs incremental.
- Si cambió la metodología, se señala aparte; no se atribuye a corrección de fuente.
- La nota del boletín se genera desde esta conciliación estructurada con evidencias.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow
from db.models_sisc_cifras import SiscCifrasPublication
from services.indicator_calculation import calculate_indicator
from services.indicator_catalog import METHODOLOGY_VERSION


def _snapshot_map(db: Session, ingestion_id: UUID) -> Dict[str, list]:
    """Foto de entrega agrupada por IDENTIDAD (no por clave de fila).

    Varias víctimas del mismo hecho comparten identidad con contenidos distintos;
    la correspondencia entre entregas se hace por identidad. Claves legado sin '#'
    se tratan como su propia identidad.
    """
    from services.sabana_history import record_identity_of
    rows = db.query(SabanaSnapshotRow).filter(SabanaSnapshotRow.ingestion_id == ingestion_id).all()
    grouped: Dict[str, list] = {}
    for r in rows:
        ident = record_identity_of(r.record_key)
        grouped.setdefault(ident, []).append({
            "record_key": r.record_key,
            "hecho_key": r.hecho_key,
            "content_hash": r.content_hash,
            "conducta": r.conducta_estandar,
            "barrio": r.barrio_normalizado,
            "fecha": r.fecha_evento.isoformat() if r.fecha_evento else None,
            "confidence": r.identity_confidence,
        })
    return grouped


def reconcile_publication(
    db: Session,
    publication_id: str,
    new_source_version_id: str,
) -> Dict[str, Any]:
    """Repite los filtros/metodología de una publicación con una entrega nueva."""
    try:
        pub_uuid = UUID(str(publication_id))
    except ValueError:
        raise ValueError(f"publication_id inválido: {publication_id}")
    row = db.query(SiscCifrasPublication).filter(SiscCifrasPublication.id == pub_uuid).first()
    if not row:
        raise ValueError(f"No existe la publicación {publication_id}")

    pub = dict(row.publication_json or {})
    period = pub.get("period") or {"start": row.period_start.isoformat(), "end": row.period_end.isoformat()}
    start = date.fromisoformat(period["start"])
    end = date.fromisoformat(period["end"])
    old_methodology = (row.methodology_version or pub.get("methodology_version") or METHODOLOGY_VERSION)
    methodology_changed = old_methodology != METHODOLOGY_VERSION

    old_sources: Dict[str, Any] = dict(row.source_version_ids or {})
    old_run_id = old_sources.get("POLICIA_SEMANAL")
    if not old_run_id:
        # Fallback: la foto vigente al momento de publicar no quedó registrada.
        old_run_id = None

    # Indicadores publicados (solo POLICIA_SEMANAL en este primer entregable).
    old_indicators = {i.get("indicator_code") or i.get("code"): i for i in pub.get("indicators", [])}

    # Recalcula con la entrega nueva, mismos filtros y metodología vigente.
    recalculated: Dict[str, Any] = {}
    for code in ("SEGURIDAD_TOTAL", "HOMICIDIO"):
        try:
            recalculated[code] = calculate_indicator(
                db,
                indicator=code,
                period_start=start,
                period_end=end,
                territory="JAMUNDI",
                source_version_id=new_source_version_id,
                methodology_version=METHODOLOGY_VERSION,
            )
        except Exception as exc:
            recalculated[code] = {"error": str(exc)}

    published_total = None
    for key in ("seguridad.total", "SEGURIDAD_TOTAL"):
        if key in old_indicators and old_indicators[key].get("value") is not None:
            published_total = int(old_indicators[key]["value"])
            break
    new_total = recalculated.get("SEGURIDAD_TOTAL", {}).get("value")

    # Clasificación por IDENTIDAD (solo si hay dos fotos comparables). Una identidad
    # con distinto número de filas entre entregas (p. ej. menos víctimas) es
    # modificación, no eliminación: ausente solo si la identidad falta por completo.
    classification: Dict[str, Any] = {"altas": 0, "modificaciones": 0, "reclasificaciones": 0, "ausentes": 0, "detalle": []}
    if old_run_id:
        try:
            old_map = _snapshot_map(db, UUID(str(old_run_id)))
            new_map = _snapshot_map(db, UUID(str(new_source_version_id)))

            def _contents(rows: list) -> set:
                return {r.get("content_hash") or r.get("record_key") for r in rows}

            def _conductas(rows: list) -> set:
                return {r.get("conducta") or "" for r in rows}

            for ident, new_rows in new_map.items():
                old_rows = old_map.get(ident)
                if old_rows is None:
                    classification["altas"] += len(new_rows)
                    continue
                if _contents(new_rows) == _contents(old_rows):
                    continue
                if _conductas(new_rows) != _conductas(old_rows):
                    classification["reclasificaciones"] += 1
                    classification["detalle"].append({"tipo": "reclasificacion", "record": ident,
                                                      "antes": sorted(_conductas(old_rows)), "ahora": sorted(_conductas(new_rows))})
                else:
                    classification["modificaciones"] += 1
                    if len(classification["detalle"]) < 20:
                        classification["detalle"].append({"tipo": "modificacion", "record": ident,
                                                          "filas_antes": len(old_rows), "filas_ahora": len(new_rows)})
            for ident, old_rows in old_map.items():
                if ident not in new_map:
                    classification["ausentes"] += len(old_rows)
            # Ausente ≠ eliminado: por sí solo no prueba eliminación ni corrección confirmada.
            classification["nota_ausentes"] = (
                "Ausente en la entrega nueva no significa eliminado ni corregido: "
                "una entrega con menos víctimas/filas no prueba por sí sola una eliminación; "
                "depende de si la fuente entrega sábana completa o archivo incremental. "
                "No presentar ausencias como correcciones confirmadas."
            )
        except Exception as exc:
            classification["error"] = str(exc)
    else:
        classification["nota"] = "La publicación original no registró source_version_id; solo se compara a nivel indicador."

    diferencia = (new_total - published_total) if (published_total is not None and new_total is not None) else None

    # Nota de boletín generada desde la conciliación estructurada.
    if diferencia is None:
        nota = "No fue posible conciliar: falta el valor publicado o el recalculado."
    elif diferencia == 0 and classification.get("reclasificaciones", 0) > 0:
        nota = (f"Sin cambio neto ({published_total}), pero con {classification['reclasificaciones']} "
                "reclasificación(es) entre conductas. Revisar distribución por delito.")
    elif diferencia == 0:
        nota = f"Sin cambios: se mantiene en {published_total} hechos para el periodo."
    else:
        signo = "+" if diferencia > 0 else ""
        nota = (f"Publicado: {published_total}; recalculado con entrega nueva: {new_total} "
                f"({signo}{diferencia}). Altas: {classification.get('altas', 0)}, "
                f"modificaciones: {classification.get('modificaciones', 0)}, "
                f"reclasificaciones: {classification.get('reclasificaciones', 0)}, "
                f"ausentes: {classification.get('ausentes', 0)}.")
    if methodology_changed:
        nota += f" Atención: la metodología cambió ({old_methodology} → {METHODOLOGY_VERSION}); no atribuir a corrección de fuente."

    return {
        "publication_id": str(publication_id),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "publicado": {"total": published_total, "source_version_id": old_run_id, "methodology_version": old_methodology},
        "recalculado": {"total": new_total, "source_version_id": str(new_source_version_id),
                        "methodology_version": METHODOLOGY_VERSION, "indicadores": recalculated},
        "diferencia": diferencia,
        "clasificacion_registros": classification,
        "methodology_changed": methodology_changed,
        "nota_boletin": nota,
    }
