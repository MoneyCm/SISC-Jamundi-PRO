from datetime import date

from services.national_context_service import (
    comparable_national_rate,
    municipality_codes_for_year,
    national_benchmark_guard,
    population_for,
    year_over_year,
)


def test_dane_population_reference_contains_jamundi_and_the_full_municipal_universe():
    assert population_for("76364", 2025) == 193630
    assert population_for("76364", 2026) == 196875
    assert len(municipality_codes_for_year(2025)) == 1122


def test_national_context_never_turns_partial_coverage_into_a_national_rate():
    context = national_benchmark_guard(
        ["HURTO_PERSONAS_MINDEFENSA", "HOMICIDIO_MINDEFENSA"],
        date(2025, 12, 31),
        1,
        year=2025,
        population_code="76364",
    )

    assert context["available"] is False
    assert context["status"] == "PENDING_EQUIVALENT_RATE"
    assert context["population"]["municipality_total"] == 193630
    assert context["population"]["national_universe"] == 1122
    assert context["cutoff"] == "2025-12-31"

    partial = comparable_national_rate(
        year=2025,
        local_code="76364",
        local_total=793,
        national_total=793,
        covered_codes=["76364"],
        cutoffs=[date(2025, 12, 31)],
    )
    assert partial["available"] is False
    assert partial["coverage"]["observed_municipalities"] == 1
    assert partial["coverage"]["expected_municipalities"] == 1122


def test_complete_dane_coverage_enables_a_rate_comparison():
    complete = comparable_national_rate(
        year=2025,
        local_code="76364",
        local_total=793,
        national_total=1123,
        covered_codes=municipality_codes_for_year(2025),
        cutoffs=[date(2025, 12, 31)],
    )

    assert complete["available"] is True
    assert complete["local_rate_per_100k"] == 409.54
    assert complete["national_rate_per_100k"] is not None
    assert complete["coverage"]["complete"] is True


def test_complete_coverage_without_one_verified_cutoff_stays_blocked():
    inconsistent = comparable_national_rate(
        year=2025,
        local_code="76364",
        local_total=793,
        national_total=1123,
        covered_codes=municipality_codes_for_year(2025),
        cutoffs=[date(2025, 11, 30), date(2025, 12, 31)],
    )

    assert inconsistent["available"] is False
    assert inconsistent["coverage"]["complete"] is True
    assert inconsistent["coverage"]["cutoff_consistent"] is False


def test_year_over_year_requires_a_real_reference_period():
    assert year_over_year(12, 10) == 20.0
    assert year_over_year(12, 0) is None
