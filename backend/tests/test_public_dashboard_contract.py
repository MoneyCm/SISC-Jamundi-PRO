from datetime import date

from api.analitica import (
    _comparison_period,
    _is_publishable_location,
    _public_conducta_label,
    _resolve_public_period,
)


def test_non_territorial_placeholders_are_not_publishable():
    assert not _is_publishable_location("BARRIO PENDIENTE POR ASIGNAR")
    assert not _is_publishable_location("NO APLICA LOCALIDAD - COMUNA")
    assert not _is_publishable_location("NAN")
    assert _is_publishable_location("TERRANOVA")


def test_public_conducta_names_hide_internal_codes():
    assert _public_conducta_label("HURTO_PERSONAS") == "Hurto a personas"
    assert _public_conducta_label("SIN_CLASIFICAR") == "Sin clasificar"
    assert _public_conducta_label("DELITO GENERAL") == "Delito General"


def test_same_period_previous_year_handles_leap_day():
    start, end = _comparison_period(date(2024, 2, 1), date(2024, 2, 29), "same_period_previous_year")
    assert start == date(2023, 2, 1)
    assert end == date(2023, 2, 28)


def test_previous_period_preserves_inclusive_length():
    start, end = _comparison_period(date(2026, 7, 1), date(2026, 7, 7), "previous_period")
    assert start == date(2026, 6, 24)
    assert end == date(2026, 6, 30)


def test_last_30_days_uses_latest_available_cutoff():
    start, end, year = _resolve_public_period(date(2026, 7, 31), None, "last_30_days", None, None)
    assert start == date(2026, 7, 2)
    assert end == date(2026, 7, 31)
    assert year == 2026
