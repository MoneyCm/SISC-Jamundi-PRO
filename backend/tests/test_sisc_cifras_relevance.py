from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.sisc_cifras_service import Indicator, SiscCifrasService, calculate_relevance, pct_change


def test_pct_change_handles_zero_previous():
    assert pct_change(10, 0) is None
    assert pct_change(15, 10) == 50


def test_relevance_rewards_change_volume_and_quality():
    validated = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="VALIDADO",
    )
    incomplete = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="INCOMPLETO",
    )
    not_publishable = calculate_relevance(
        value=40,
        variation_percentage=35,
        priority=1.0,
        quality_status="NO PUBLICABLE",
    )

    assert validated > incomplete > not_publishable
    assert not_publishable == 0


def test_saved_publication_persists_saved_governance_state(monkeypatch):
    monkeypatch.setattr(
        SiscCifrasService,
        "period_bounds",
        classmethod(lambda cls, edition, start, end: (date(2026, 7, 1), date(2026, 7, 7))),
    )
    monkeypatch.setattr(
        SiscCifrasService,
        "comparison_bounds",
        classmethod(
            lambda cls, edition, mode, start, end: (
                date(2025, 7, 1),
                date(2025, 7, 7),
                "mismo periodo del ano anterior",
                "year_over_year",
            )
        ),
    )
    monkeypatch.setattr(SiscCifrasService, "database_available", classmethod(lambda cls, db: True))
    monkeypatch.setattr(SiscCifrasService, "collect_indicators", classmethod(lambda cls, *args, **kwargs: []))
    monkeypatch.setattr(SiscCifrasService, "select_insights", classmethod(lambda cls, *args, **kwargs: []))
    monkeypatch.setattr(SiscCifrasService, "build_slides", classmethod(lambda cls, *args: []))
    monkeypatch.setattr(SiscCifrasService, "source_registry", classmethod(lambda cls, db: []))
    monkeypatch.setattr(SiscCifrasService, "publication_sources", classmethod(lambda cls, db, **kwargs: []))

    db = MagicMock()
    publication = SiscCifrasService.generate_publication(
        db,
        edition_type="weekly",
        period_start=None,
        period_end=None,
        comparison_mode="auto",
        source_codes=None,
        max_insights=5,
        created_by="analista",
        save_history=True,
    )

    saved_row = db.add.call_args.args[0]
    assert publication["governance"]["history_saved"] is True
    assert saved_row.publication_json["governance"]["history_saved"] is True
    assert publication["id"] == str(saved_row.id)


def test_coverage_status_distinguishes_aligned_partial_stale_and_missing():
    start = date(2026, 7, 1)
    end = date(2026, 7, 31)

    assert SiscCifrasService.coverage_status(10, date(2026, 7, 31), start, end) == "aligned"
    assert SiscCifrasService.coverage_status(10, date(2026, 7, 15), start, end) == "partial"
    assert SiscCifrasService.coverage_status(0, date(2026, 6, 30), start, end) == "stale"
    assert SiscCifrasService.coverage_status(0, date(2026, 8, 1), start, end) == "missing"


def test_monthly_previous_period_uses_previous_calendar_month():
    start, end, label, mode = SiscCifrasService.comparison_bounds(
        "monthly",
        "auto",
        date(2026, 7, 1),
        date(2026, 7, 31),
    )

    assert (start, end) == (date(2026, 6, 1), date(2026, 6, 30))
    assert label == "periodo anterior comparable"
    assert mode == "previous_period"


def test_partial_month_compares_the_same_days_of_previous_month():
    start, end, _, _ = SiscCifrasService.comparison_bounds(
        "monthly",
        "previous_period",
        date(2026, 7, 1),
        date(2026, 7, 14),
    )

    assert (start, end) == (date(2026, 6, 1), date(2026, 6, 14))


def test_family_batches_keep_latest_version_per_reporting_entity():
    batches = [
        SimpleNamespace(reporting_entity="Comisaria Primera", version=1, period="2026-07", created_at=datetime(2026, 7, 1)),
        SimpleNamespace(reporting_entity="Comisaria Segunda", version=2, period="2026-07", created_at=datetime(2026, 7, 1)),
        SimpleNamespace(reporting_entity=" comisaria primera ", version=3, period="2026-07", created_at=datetime(2026, 7, 2)),
        SimpleNamespace(reporting_entity="Comisaria Segunda", version=1, period="2026-06", created_at=datetime(2026, 6, 1)),
    ]

    latest = SiscCifrasService.latest_batches_by_entity(batches)

    assert [(batch.reporting_entity.strip(), batch.version) for batch in latest] == [
        ("comisaria primera", 3),
        ("Comisaria Segunda", 2),
    ]


def test_fallback_publication_exposes_non_publishable_source_contract():
    publication = SiscCifrasService.fallback_publication(
        edition_type="weekly",
        start=date(2026, 7, 5),
        end=date(2026, 7, 11),
        prev_start=date(2025, 7, 5),
        prev_end=date(2025, 7, 11),
        comparison_label="mismo periodo del ano anterior",
        comparison_mode="year_over_year",
        selected_sources=["POLICIA_SEMANAL"],
        created_by=None,
    )

    assert publication["governance"]["publication_ready"] is False
    assert publication["sources"][0]["coverage_status"] == "missing"
    assert publication["sources"][0]["publishable"] is False


def test_weekly_bulletin_uses_context_when_no_exact_family_data():
    from datetime import datetime

    june_batch = SimpleNamespace(
        id="batch-jun",
        program="COMISARIAS",
        reporting_entity="Comisaria Central",
        period="2026-06",
        version=1,
        validation_status="APPROVED",
        cutoff_date=date(2026, 6, 30),
        reporting_basis="CUMULATIVE",
        created_at=datetime(2026, 6, 30),
        indicators=[
            SimpleNamespace(
                id="ind-1",
                indicator="Atenciones por VIIF",
                value=25.0,
                unit="casos",
                is_public=True,
                privacy_threshold=10,
                category="Familia",
            )
        ],
    )

    db = MagicMock()
    mock_query = MagicMock()
    db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [june_batch]

    exact = SiscCifrasService.family_indicators(
        db,
        date(2026, 7, 21),
        date(2026, 7, 27),
        date(2025, 7, 21),
        date(2025, 7, 27),
        edition_type="weekly",
    )

    context = SiscCifrasService.family_context_indicators(
        db,
        date(2026, 7, 21),
        date(2026, 7, 27),
        edition_type="weekly",
    )

    assert len(exact) == 0, "Weekly period should not have EXACT family data"
    assert len(context) >= 1, "Weekly period should get CONTEXT from previous closed month"
    assert all(ind.metadata.get("coverage_type") == "CONTEXT" for ind in context)
    assert all(ind.comparison_value is None for ind in context)


def test_operational_summary_reuses_period_for_inspections_and_family(monkeypatch):
    source_rows = [
        {"code": "INSPECCIONES_RNMC", "included": True, "coverage_status": "partial"},
        {"code": "COMISARIAS_FAMILIA", "included": False, "coverage_status": "stale"},
    ]
    captured = {}
    indicator = Indicator(
        id="INSPECCIONES_RNMC:convivencia.actuaciones:TOTAL",
        source="Inspecciones de Policia / RNMC",
        source_code="INSPECCIONES_RNMC",
        domain="CONVIVENCIA",
        category="Actuaciones",
        indicator_code="convivencia.actuaciones",
        indicator_name="Actuaciones registradas",
        value=25,
        unit="actuaciones registradas",
        period_start="2026-07-01",
        period_end="2026-07-31",
        geography=None,
        comparison_value=20,
        variation_absolute=5,
        variation_percentage=25,
        quality_status="VALIDADO",
        publication_level="PUBLICO",
        cutoff_date="2026-07-14",
        metadata={},
    )

    monkeypatch.setattr(SiscCifrasService, "database_available", classmethod(lambda cls, db: True))
    monkeypatch.setattr(
        SiscCifrasService,
        "publication_sources",
        classmethod(lambda cls, db, **kwargs: source_rows),
    )

    def collect(cls, db, start, end, prev_start, prev_end, source_codes, edition_type):
        captured.update({
            "start": start,
            "end": end,
            "source_codes": source_codes,
            "edition_type": edition_type,
        })
        return [indicator]

    monkeypatch.setattr(SiscCifrasService, "collect_indicators", classmethod(collect))

    summary = SiscCifrasService.operational_summary(
        MagicMock(),
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        comparison_mode="previous_year",
    )

    assert summary["period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert summary["comparison_period"] == {"start": "2025-07-01", "end": "2025-07-31"}
    assert summary["sources"] == source_rows
    assert summary["indicators"][0]["value"] == 25
    assert captured == {
        "start": date(2026, 7, 1),
        "end": date(2026, 7, 31),
        "source_codes": ["INSPECCIONES_RNMC"],
        "edition_type": "monthly",
    }
