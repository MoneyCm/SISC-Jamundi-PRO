"""Guardrails for the historical MinDefensa context module.

The source currently provides historical counts, but not the population and
coverage contract required to compare a municipality against a national rate.
These helpers keep the API from turning a raw count average into a misleading
percentage.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional


NATIONAL_BENCHMARK_REQUIREMENTS = [
    "poblacion homologada para cada territorio",
    "cobertura verificable de municipios para el mismo corte",
    "definicion equivalente de la conducta y del periodo",
]


def year_over_year(current: int, reference: int) -> Optional[float]:
    """Return a comparable year-over-year percentage or ``None`` without base."""
    if reference <= 0:
        return None
    return round(((current - reference) / reference) * 100, 1)


def national_benchmark_guard(
    source_ids: Iterable[str],
    cutoff: Optional[date],
    municipalities_loaded: int,
) -> dict:
    """Describe why an unweighted national count average must not be displayed."""
    return {
        "available": False,
        "status": "PENDING_EQUIVALENT_RATE",
        "title": "Referencia nacional pendiente de homologacion",
        "reason": (
            "No se publica una comparacion nacional porque la serie cargada no "
            "incluye una tasa equivalente por poblacion y cobertura verificable "
            "para el mismo corte."
        ),
        "requirements": NATIONAL_BENCHMARK_REQUIREMENTS,
        "source_ids": sorted({source_id for source_id in source_ids if source_id}),
        "cutoff": cutoff.isoformat() if cutoff else None,
        "municipalities_loaded": municipalities_loaded,
    }
