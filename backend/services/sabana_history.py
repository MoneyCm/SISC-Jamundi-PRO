"""Identidad estable y resumen de cobertura para entregas SABANA."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from datetime import date
from decimal import Decimal


def normalize_source_id(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "nat"}:
        return ""
    return text


def snapshot_hecho_key(source_id: str, fingerprint: str) -> str:
    source_id = normalize_source_id(source_id)
    return f"ID:{source_id}" if source_id else f"FP:{fingerprint}"

def stable_record_key(payload: dict) -> str:
    """Huella del CONTENIDO: identifica una copia exacta sin confundir victimas.

    LEGADO: se usaba como identidad. No usar como única identidad estable:
    barrio/fecha/conducta pueden corregirse y generarían un registro "nuevo"
    en vez de una corrección. Ver build_record_identity() + content_hash().
    """
    return content_hash(payload)


def content_hash(payload: dict) -> str:
    """Huella del contenido: detecta que los valores cambiaron."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_record_identity(source_id: str, fingerprint: str) -> dict:
    """Identidad del registro: permite reconocerlo entre entregas.

    - Con ID oficial (HECHOS_ID): identidad estable ID:<id>, confianza HIGH.
    - Sin ID: fallback a fingerprint (hecho+víctima), confianza UNCERTAIN.
      No presentar coincidencia aproximada como corrección confirmada.
    """
    clean = normalize_source_id(source_id)
    if clean:
        return {"record_identity": f"ID:{clean}", "confidence": "HIGH"}
    return {"record_identity": f"FP:{fingerprint}", "confidence": "UNCERTAIN"}


def build_snapshot_record_key(record_identity: str, payload_hash: str) -> str:
    """Clave estable de FILA: identidad + huella de contenido.

    Varias víctimas del mismo hecho comparten identidad pero tienen contenido
    distinto, por lo que cada una conserva su fila. Una copia exacta repetida
    (reintento del mismo archivo) produce la misma clave y se deduplica.
    Una corrección (misma identidad, distinto contenido) produce otra clave;
    la correspondencia entre entregas se hace por identidad, no por clave.
    """
    return f"{record_identity}#{payload_hash[:12]}"


def record_identity_of(record_key: str) -> str:
    """Extrae la identidad de una clave de fila (compatible con legado sin '#')."""
    return str(record_key or "").split("#", 1)[0]


def claim_snapshot_record(seen: set[str], record_key: str) -> bool:
    """Registra una fila una sola vez dentro de la misma entrega."""
    if record_key in seen:
        return False
    seen.add(record_key)
    return True


def build_coverage(dates_and_weeks: Iterable[tuple[date, int | None]]) -> dict:
    items = list(dates_and_weeks)
    if not items:
        return {"years": [], "min_date": None, "max_date": None, "max_week_by_year": {}}

    years = sorted({item_date.year for item_date, _ in items})
    max_week_by_year: dict[str, int] = {}
    for item_date, week in items:
        if week is None:
            continue
        year_key = str(item_date.year)
        max_week_by_year[year_key] = max(max_week_by_year.get(year_key, 0), week)

    dates = [item_date for item_date, _ in items]
    return {
        "years": years,
        "min_date": min(dates).isoformat(),
        "max_date": max(dates).isoformat(),
        "max_week_by_year": max_week_by_year,
    }