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
    """Identifica una copia exacta sin confundir victimas del mismo hecho."""
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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