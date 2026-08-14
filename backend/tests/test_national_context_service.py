from datetime import date

from services.national_context_service import national_benchmark_guard, year_over_year


def test_national_context_never_turns_raw_counts_into_a_national_percentage():
    context = national_benchmark_guard(
        ["HURTO_PERSONAS_MINDEFENSA", "HOMICIDIO_MINDEFENSA"],
        date(2025, 12, 31),
        1122,
    )

    assert context["available"] is False
    assert context["status"] == "PENDING_EQUIVALENT_RATE"
    assert "por poblacion" in context["reason"]
    assert "percentage" not in context
    assert context["cutoff"] == "2025-12-31"


def test_year_over_year_requires_a_real_reference_period():
    assert year_over_year(12, 10) == 20.0
    assert year_over_year(12, 0) is None
