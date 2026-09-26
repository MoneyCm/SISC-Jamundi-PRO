"""Boletín mensual: Medicina Legal con su periodo propio y recordatorio en la portada."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from db.models_sisc_cifras import SiscCifrasPublication
from db.session import engine
from services import medicina_legal_bulletin as ml
from services import observatory_service
from services.sisc_cifras_service import SiscCifrasService


def test_window_uses_months_the_source_covers():
    window = ml.plan_window(date(2026, 3, 1), date(2026, 3, 31), latest=202606)
    assert (window.first, window.last, window.aligned) == (202603, 202603, True)
    assert window.previous == (202503, 202503)


def test_window_falls_back_to_latest_month_as_context():
    window = ml.plan_window(date(2026, 8, 1), date(2026, 8, 31), latest=202606)
    assert (window.first, window.last, window.aligned, window.label) == (202606, 202606, False, "junio de 2026")


def test_semester_publishes_the_covered_part():
    window = ml.plan_window(date(2026, 1, 1), date(2026, 6, 30), latest=202604)
    assert (window.label, window.aligned) == ("enero a abril de 2026", False)
    assert ml.range_label(202511, 202602) == "noviembre de 2025 a febrero de 2026"
    assert ml.month_end(202602) == date(2026, 2, 28)


def test_medicina_legal_does_not_apply_to_weekly():
    source = SiscCifrasService._medicina_legal_source(None, {"code": "MEDICINA_LEGAL"}, "weekly",
                                                       date(2026, 9, 6), date(2026, 9, 12))
    assert source["coverage_status"] == "not_applicable"


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def publish(db, edition, start, end):
    db.add(SiscCifrasPublication(title="SISC EN CIFRAS", edition_type=edition, period_start=start,
                                 period_end=end, status="PUBLISHED", publication_json={}))
    db.flush()


def test_monthly_reminder_first_week_then_late(db):
    [row] = observatory_service.monthly_bulletin_signals(db, date(2031, 3, 4))
    assert (row["level"], row["title"]) == ("MEDIA", "Toca el boletín mensual de febrero de 2031")
    [row] = observatory_service.monthly_bulletin_signals(db, date(2031, 3, 12))
    assert (row["level"], row["title"]) == ("ALTA", "Boletín mensual de febrero de 2031 atrasado")
    publish(db, "monthly", date(2031, 2, 1), date(2031, 2, 28))
    [row] = observatory_service.monthly_bulletin_signals(db, date(2031, 3, 12))
    assert row["level"] == "OK"


def test_weekly_signal_ignores_monthly_editions(db):
    publish(db, "monthly", date(2031, 2, 1), date(2031, 2, 28))
    weekly = observatory_service.bulletin_signals(db, date(2031, 3, 4))[0]
    assert "semanal" in weekly["title"] and weekly["level"] != "OK"
    publish(db, "weekly", date(2031, 2, 23), date(2031, 3, 1))
    assert observatory_service.bulletin_signals(db, date(2031, 3, 4))[0]["title"] == "Boletín semanal al día"
