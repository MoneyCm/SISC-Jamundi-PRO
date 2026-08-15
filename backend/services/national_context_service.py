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
REFERENCE_DEPARTMENTS = ("76", "19")  # Valle del Cauca y Cauca


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
def _population_reference() -> tuple[
    dict[tuple[str, int], int],
    dict[tuple[str, int], str],
    dict[tuple[str, int], str],
]:
    if not POPULATION_FILE.exists():
        raise FileNotFoundError(f"DANE population reference not found: {POPULATION_FILE}")

    population: dict[tuple[str, int], int] = {}
    municipality_names: dict[tuple[str, int], str] = {}
    department_names: dict[tuple[str, int], str] = {}
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
                department_names[(code, year)] = row.get("department", "")
    return population, municipality_names, department_names


def population_for(code: object, year: int) -> Optional[int]:
    normalized_code = normalize_municipality_code(code)
    if not normalized_code:
        return None
    return _population_reference()[0].get((normalized_code, year))


def municipality_codes_for_year(year: int) -> set[str]:
    population, _, _ = _population_reference()
    return {code for code, population_year in population if population_year == year}


def municipality_code_for_name(name: object, year: int) -> Optional[str]:
    _, names, _ = _population_reference()
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

    _, names, _ = _population_reference()
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


def population_peer_codes(
    code: object,
    year: int,
    *,
    department_codes: tuple[str, ...] = REFERENCE_DEPARTMENTS,
    lower_population_ratio: float = 0.5,
    upper_population_ratio: float = 2.0,
) -> set[str]:
    """Return nearby municipalities with a transparent, comparable population range."""
    target_code = normalize_municipality_code(code)
    target_population = population_for(target_code, year)
    if not target_code or not target_population:
        return set()

    population, _, _ = _population_reference()
    return {
        candidate_code
        for candidate_code in municipality_codes_for_year(year)
        if candidate_code != target_code
        and candidate_code[:2] in department_codes
        and lower_population_ratio
        <= (population[(candidate_code, year)] / target_population)
        <= upper_population_ratio
    }


def national_municipal_ranking(
    *,
    year: int,
    target_code: object,
    totals_by_code: dict[object, int],
) -> list[dict]:
    """Rank the full DANE municipal universe by an equivalent registered rate."""
    population, names, departments = _population_reference()
    normalized_target = normalize_municipality_code(target_code)
    normalized_totals = {
        code: max(int(total), 0)
        for raw_code, total in totals_by_code.items()
        if (code := normalize_municipality_code(raw_code)) is not None
    }
    rows = []
    for code in municipality_codes_for_year(year):
        municipality_population = population.get((code, year))
        cases = normalized_totals.get(code, 0)
        rows.append({
            "codigo_dane": code,
            "departamento": departments.get((code, year), ""),
            "municipio": names.get((code, year), code),
            "casos": cases,
            "poblacion": municipality_population,
            "tasa_por_100k": rate_per_100k(cases, municipality_population),
            "es_objetivo": code == normalized_target,
        })

    rows.sort(key=lambda row: (-(row["tasa_por_100k"] or 0), row["municipio"]))
    for position, row in enumerate(rows, start=1):
        row["posicion_nacional"] = position
    return rows


def rate_per_100k(count: int, population: Optional[int]) -> Optional[float]:
    if population is None or population <= 0:
        return None
    return round((count / population) * 100000, 2)


def year_over_year(current: int, reference: int) -> Optional[float]:
    """Return a comparable year-over-year percentage or ``None`` without base."""
    if reference <= 0:
        return None
    return round(((current - reference) / reference) * 100, 1)


def named_territorial_comparison(
    *,
    year: int,
    target_code: object,
    target_total: int,
    expected_codes: Iterable[object],
    totals_by_code: dict[object, int],
    covered_codes: Iterable[object],
    cutoffs: Iterable[date] = (),
) -> dict:
    """Build an auditable municipal ranking using equivalent DANE rates."""
    normalized_target = normalize_municipality_code(target_code)
    normalized_expected = {
        code for raw_code in expected_codes
        if (code := normalize_municipality_code(raw_code)) is not None
        and code != normalized_target
        and population_for(code, year) is not None
    }
    normalized_covered = {
        code for raw_code in covered_codes
        if (code := normalize_municipality_code(raw_code)) in normalized_expected
    }
    normalized_totals = {
        code: max(int(total), 0)
        for raw_code, total in totals_by_code.items()
        if (code := normalize_municipality_code(raw_code)) is not None
    }
    cutoff_values = {cutoff for cutoff in cutoffs if cutoff is not None}
    comparable_cutoff = next(iter(cutoff_values)) if len(cutoff_values) == 1 else None
    target_population = population_for(normalized_target, year)
    target_rate = rate_per_100k(target_total, target_population)

    rows = [{
        "codigo_dane": normalized_target,
        "municipio": municipality_name_for_code(normalized_target, year) or str(normalized_target or "Municipio objetivo"),
        "casos": max(int(target_total), 0),
        "poblacion": target_population,
        "tasa_por_100k": target_rate,
        "diferencia_tasa_objetivo": 0.0 if target_rate is not None else None,
        "diferencia_porcentual_objetivo": 0.0 if target_rate is not None else None,
        "es_objetivo": True,
        "disponible": target_rate is not None,
    }]
    for code in normalized_expected:
        population = population_for(code, year)
        available = code in normalized_covered and code in normalized_totals and population is not None
        total = normalized_totals.get(code) if available else None
        rate = rate_per_100k(total, population) if total is not None else None
        rate_difference = round(rate - target_rate, 2) if rate is not None and target_rate is not None else None
        relative_difference = (
            round((rate_difference / target_rate) * 100, 1)
            if rate_difference is not None and target_rate and target_rate > 0 else None
        )
        rows.append({
            "codigo_dane": code,
            "municipio": municipality_name_for_code(code, year) or code,
            "casos": total,
            "poblacion": population,
            "tasa_por_100k": rate,
            "diferencia_tasa_objetivo": rate_difference,
            "diferencia_porcentual_objetivo": relative_difference,
            "es_objetivo": False,
            "disponible": available and rate is not None,
        })

    ranked_rows = sorted(
        (row for row in rows if row["disponible"]),
        key=lambda row: (-row["tasa_por_100k"], row["municipio"]),
    )
    rank_by_code = {row["codigo_dane"]: rank for rank, row in enumerate(ranked_rows, start=1)}
    for row in rows:
        row["posicion"] = rank_by_code.get(row["codigo_dane"])
    rows.sort(key=lambda row: (row["posicion"] is None, row["posicion"] or 9999, row["municipio"]))

    return {
        "available": bool(target_rate is not None and len(ranked_rows) > 1 and comparable_cutoff),
        "year": year,
        "cutoff": comparable_cutoff.isoformat() if comparable_cutoff else None,
        "target_code": normalized_target,
        "expected_municipalities": len(normalized_expected),
        "observed_municipalities": len(normalized_covered),
        "coverage_complete": normalized_expected <= normalized_covered and bool(normalized_expected),
        "rows": rows,
        "methodology": (
            "Municipios de Valle del Cauca y Cauca con poblacion entre 50% y 200% "
            "de la poblacion del municipio objetivo; tasas por 100.000 habitantes con poblacion DANE."
        ),
    }


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
    official_scope_verified: bool = False,
) -> dict:
    """Calculate a national rate from an official nationwide source.

    Event workbooks omit municipalities with zero reported cases. A trusted
    national aggregate therefore verifies scope at file level instead of
    requiring one event row for every DANE municipality.
    """
    event_codes = {
        code for raw_code in covered_codes
        if (code := normalize_municipality_code(raw_code)) is not None
    }
    comparison_codes = municipality_codes_for_year(year) if official_scope_verified else event_codes
    result = comparable_reference_rate(
        year=year,
        local_code=local_code,
        local_total=local_total,
        reference_total=national_total,
        expected_codes=municipality_codes_for_year(year),
        covered_codes=comparison_codes,
        cutoffs=cutoffs,
    )
    result["national_population"] = result["reference_population"]
    result["national_rate_per_100k"] = result["reference_rate_per_100k"]
    result["coverage"].update({
        "official_scope_verified": official_scope_verified,
        "municipalities_with_reported_cases": len(event_codes),
        "verification_basis": (
            "Archivo nacional oficial procesado de forma completa; los municipios ausentes se interpretan como cero casos."
            if official_scope_verified
            else "Cobertura inferida a partir de municipios con registros."
        ),
    })
    return result


def comparable_reference_rate(
    *,
    year: int,
    local_code: object,
    local_total: int,
    reference_total: int,
    expected_codes: Iterable[object],
    covered_codes: Iterable[object],
    cutoffs: Iterable[date] = (),
) -> dict:
    """Calculate a rate only when all reference municipalities share one cutoff."""
    expected_codes = {
        code for raw_code in expected_codes
        if (code := normalize_municipality_code(raw_code)) is not None
        and population_for(code, year) is not None
    }
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
        "reference_population": None,
        "reference_rate_per_100k": None,
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
        result["reason"] = "No hay municipios de referencia con poblacion DANE para el ano consultado."
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

    reference_population = sum(population_for(code, year) or 0 for code in expected_codes)
    reference_rate = rate_per_100k(reference_total, reference_population)
    result.update({
        "available": True,
        "reference_population": reference_population,
        "reference_rate_per_100k": reference_rate,
        "rate_difference_per_100k": round(local_rate - reference_rate, 2),
    })
    return result
