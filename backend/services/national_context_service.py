"""Comparable national-context calculations backed by official DANE population.

National comparisons are only valid when the crime source covers the full DANE
municipal universe for the same year and conduct. Partial data remains useful
for local trends, but is not allowed to produce a national rate.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "reference"
POPULATION_FILE = REFERENCE_DIR / "dane_population_municipal_2018_2042.csv"
NATIONAL_BENCHMARK_REQUIREMENTS = [
    "poblacion DANE para cada municipio",
    "cobertura completa de municipios para la misma conducta y ano",
    "misma definicion de conducta, periodo y corte",
]


def normalize_municipality_code(value: object) -> Optional[str]:
    """Normalize a DANE municipality code without silently accepting bad data."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    return digits.zfill(5)


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.upper().split())


@lru_cache(maxsize=1)
def _population_reference() -> tuple[dict[tuple[str, int], int], dict[tuple[str, int], str]]:
    if not POPULATION_FILE.exists():
        raise FileNotFoundError(f"DANE population reference not found: {POPULATION_FILE}")

    population: dict[tuple[str, int], int] = {}
    municipality_names: dict[tuple[str, int], str] = {}
    with POPULATION_FILE.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            code = normalize_municipality_code(row.get("municipality_code"))
            try:
                year = int(row.get("year", ""))
                total = int(row.get("population", ""))
            except (TypeError, ValueError):
                continue
            if code and total > 0:
                population[(code, year)] = total
                municipality_names[(code, year)] = row.get("municipality", "")
    return population, municipality_names


def population_for(code: object, year: int) -> Optional[int]:
    normalized_code = normalize_municipality_code(code)
    if not normalized_code:
        return None
    return _population_reference()[0].get((normalized_code, year))


def municipality_codes_for_year(year: int) -> set[str]:
    population, _ = _population_reference()
    return {code for code, population_year in population if population_year == year}


def municipality_code_for_name(name: object, year: int) -> Optional[str]:
    _, names = _population_reference()
    target = normalize_name(name)
    for (code, population_year), municipality_name in names.items():
        if population_year == year and normalize_name(municipality_name) == target:
            return code
    return None


def municipality_name_for_code(code: object, year: Optional[int] = None) -> Optional[str]:
    """Return the official DANE municipality name for a municipality code."""
    normalized_code = normalize_municipality_code(code)
    if not normalized_code:
        return None

    _, names = _population_reference()
    if year is not None:
        name = names.get((normalized_code, int(year)))
        if name:
            return name

    candidates = sorted(
        (reference_year, name)
        for (reference_code, reference_year), name in names.items()
        if reference_code == normalized_code
    )
    return candidates[0][1] if candidates else None


def rate_per_100k(count: int, population: Optional[int]) -> Optional[float]:
    if population is None or population <= 0:
        return None
    return round((count / population) * 100000, 2)


def year_over_year(current: int, reference: int) -> Optional[float]:
    """Return a comparable year-over-year percentage or ``None`` without base."""
    if reference <= 0:
        return None
    return round(((current - reference) / reference) * 100, 1)


def national_benchmark_guard(
    source_ids: Iterable[str],
    cutoff: Optional[date],
    municipalities_loaded: int,
    *,
    year: Optional[int] = None,
    population_code: Optional[str] = None,
) -> dict:
    """Return provenance and the guard that protects against false comparison."""
    local_population = population_for(population_code, year) if year and population_code else None
    expected = municipality_codes_for_year(year) if year else set()
    return {
        "available": False,
        "status": "PENDING_EQUIVALENT_RATE",
        "title": "Referencia nacional pendiente de cobertura verificable",
        "reason": (
            "No se publica una comparacion nacional hasta verificar cobertura "
            "municipal completa para la misma conducta, ano y corte."
        ),
        "requirements": NATIONAL_BENCHMARK_REQUIREMENTS,
        "source_ids": sorted({source_id for source_id in source_ids if source_id}),
        "cutoff": cutoff.isoformat() if cutoff else None,
        "municipalities_loaded": municipalities_loaded,
        "population": {
            "source": "DANE - Proyecciones municipales CNPV 2018",
            "source_url": "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx",
            "year": year,
            "municipality_code": normalize_municipality_code(population_code),
            "municipality_total": local_population,
            "national_universe": len(expected),
        },
    }


def comparable_national_rate(
    *,
    year: int,
    local_code: object,
    local_total: int,
    national_total: int,
    covered_codes: Iterable[object],
    cutoffs: Iterable[date] = (),
) -> dict:
    """Calculate comparable rates only for a complete DANE municipal coverage."""
    expected_codes = municipality_codes_for_year(year)
    observed_codes = {
        code for raw_code in covered_codes
        if (code := normalize_municipality_code(raw_code)) in expected_codes
    }
    missing_codes = expected_codes - observed_codes
    cutoff_values = {cutoff for cutoff in cutoffs if cutoff is not None}
    comparable_cutoff = next(iter(cutoff_values)) if len(cutoff_values) == 1 else None
    local_population = population_for(local_code, year)
    local_rate = rate_per_100k(local_total, local_population)
    coverage = round((len(observed_codes) / len(expected_codes)) * 100, 2) if expected_codes else 0.0

    result = {
        "available": False,
        "year": year,
        "local_population": local_population,
        "local_rate_per_100k": local_rate,
        "national_rate_per_100k": None,
        "coverage": {
            "expected_municipalities": len(expected_codes),
            "observed_municipalities": len(observed_codes),
            "percentage": coverage,
            "missing_municipalities": len(missing_codes),
            "complete": not missing_codes and bool(expected_codes),
            "cutoff": comparable_cutoff.isoformat() if comparable_cutoff else None,
            "cutoff_consistent": comparable_cutoff is not None,
        },
        "reason": None,
    }
    if not expected_codes:
        result["reason"] = "No hay universo poblacional DANE para el ano consultado."
        return result
    if local_population is None:
        result["reason"] = "No hay poblacion DANE homologada para el municipio consultado."
        return result
    if missing_codes:
        result["reason"] = "La cobertura de la fuente no es completa para esta conducta y ano."
        return result
    if comparable_cutoff is None:
        result["reason"] = "La fuente no tiene un corte unico verificable para esta conducta."
        return result

    national_population = sum(population_for(code, year) or 0 for code in expected_codes)
    result.update({
        "available": True,
        "national_population": national_population,
        "national_rate_per_100k": rate_per_100k(national_total, national_population),
        "rate_difference_per_100k": round(local_rate - rate_per_100k(national_total, national_population), 2),
    })
    return result
