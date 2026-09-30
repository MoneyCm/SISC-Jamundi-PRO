from datetime import date

from services.sisc_cifras_service import SiscCifrasService


def insight(current, previous):
    indicator = SiscCifrasService.indicator(
        source="Fuente", source_code="TEST", domain="SEGURIDAD", category="Hechos",
        code="hurtos", name="Hurtos", value=current, unit="registros",
        start=date(2026, 7, 1), end=date(2026, 7, 31),
        comparison_value=previous, cutoff=date(2026, 8, 15), priority=1,
    )
    return SiscCifrasService.insight_from_indicator(indicator, "periodo anterior").detail


def test_comparable_insight_keeps_both_counts_and_indicator():
    text = insight(40, 50)
    assert "Hurtos: 40 registros frente a 50" in text
    assert "20.0%" in text


def test_non_comparable_and_small_counts_keep_indicator():
    assert "Hurtos: 25 registros" in insight(25, None)
    assert "Hurtos: 5 registros frente a 8" in insight(5, 8)


def test_zero_baseline_is_distinguished_from_missing_data():
    text = insight(25, 0)
    assert "frente a 0" in text
    assert "base cero" in text
    assert "sin base comparable" not in text
