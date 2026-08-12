from datetime import date
from unittest.mock import MagicMock

from services.sisc_cifras_service import SiscCifrasService, calculate_relevance, pct_change


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
    monkeypatch.setattr(SiscCifrasService, "collect_indicators", classmethod(lambda cls, *args: []))
    monkeypatch.setattr(SiscCifrasService, "select_insights", classmethod(lambda cls, *args, **kwargs: []))
    monkeypatch.setattr(SiscCifrasService, "build_slides", classmethod(lambda cls, *args: []))
    monkeypatch.setattr(SiscCifrasService, "source_registry", classmethod(lambda cls, db: []))

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
