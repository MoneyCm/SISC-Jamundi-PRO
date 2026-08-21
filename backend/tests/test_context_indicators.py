"""
Context indicators — Temporal policy, coverage propagation, and contract compliance.
Tests for the contextual Comisarias data used by weekly bulletins.
"""
from collections import defaultdict
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.sisc_cifras_service import SiscCifrasService


def _batch(program, entity, period, cutoff, *,
           version=1, status="APPROVED", created=None, indicators=None):
    return SimpleNamespace(
        id=f"batch-{entity}-{period}-v{version}",
        program=program,
        reporting_entity=entity,
        period=period,
        version=version,
        validation_status=status,
        cutoff_date=cutoff,
        reporting_basis="CUMULATIVE",
        created_at=created or datetime(2026, 1, 1),
        indicators=indicators or [],
    )


def _ind(name, value, *, is_public=True, privacy_threshold=10):
    return SimpleNamespace(
        id=f"ind-{name}",
        indicator=name,
        value=float(value),
        unit="casos",
        is_public=is_public,
        privacy_threshold=privacy_threshold,
        category="Familia",
    )


def _with_context(batches):
    """Patch _latest_approved_context_batch to return the given batches, deduplicated."""
    deduped = SiscCifrasService.latest_batches_by_entity(batches)
    return patch.object(SiscCifrasService, '_latest_approved_context_batch', return_value=deduped)


def _eval_sa_expr(batches, expr):
    """Evaluate a single SQLAlchemy BinaryExpression against SimpleNamespace objects."""
    if not hasattr(expr, 'left') or not hasattr(expr, 'right'):
        return batches
    left, right = expr.left, expr.right
    col_name = getattr(left, 'name', None) or getattr(right, 'name', None)
    value = getattr(left, 'value', None)
    if value is None or (isinstance(value, str) and value.startswith(':')):
        value = getattr(right, 'value', None)
    if col_name is None or value is None:
        return batches
    op_name = expr.operator.__name__ if hasattr(expr.operator, '__name__') else str(expr.operator)
    result = []
    for b in batches:
        bval = getattr(b, col_name, None)
        if bval is None:
            continue
        cmp_val = value
        if isinstance(bval, datetime) and isinstance(value, date) and not isinstance(value, datetime):
            cmp_val = datetime.combine(value, datetime.min.time())
        elif isinstance(bval, date) and isinstance(value, datetime) and not isinstance(bval, datetime):
            bval = datetime.combine(bval, datetime.min.time())
        try:
            if op_name == 'eq' and bval == cmp_val:
                result.append(b)
            elif op_name == 'ne' and bval != cmp_val:
                result.append(b)
            elif op_name == 'le' and bval <= cmp_val:
                result.append(b)
            elif op_name == 'lt' and bval < cmp_val:
                result.append(b)
            elif op_name == 'ge' and bval >= cmp_val:
                result.append(b)
            elif op_name == 'gt' and bval > cmp_val:
                result.append(b)
        except TypeError:
            continue
    return result


def _mock_db_sql(all_batches):
    """Mock DB that evaluates SQLAlchemy filter() predicates against SimpleNamespace objects."""
    db = MagicMock()

    def make_query(model):
        captured = list(all_batches)

        q = MagicMock()

        def do_filter(*args, **kwargs):
            nonlocal captured
            for expr in args:
                captured = _eval_sa_expr(captured, expr)
            return q

        q.filter.side_effect = do_filter
        q.order_by.return_value = q
        q.all.side_effect = lambda: list(captured)
        return q

    db.query.side_effect = make_query
    return db


class TestContextTemporalPolicy:

    def test_weekly_july_excludes_july_batch(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1))
        jul = _batch("COMISARIAS", "E1", "2026-07", date(2026, 7, 31),
                     created=datetime(2026, 8, 1))

        db = _mock_db_sql([jun, jul])
        result = SiscCifrasService._latest_approved_context_batch(
            db, "COMISARIAS", date(2026, 7, 27),
        )
        periods = {b.period for b in result}
        assert "2026-07" not in periods, "July batch excluded by cutoff_date <= period_end"

    def test_late_cutoff_excludes_batch(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 7, 5),
                     created=datetime(2026, 7, 1))

        db = _mock_db_sql([jun])
        result = SiscCifrasService._latest_approved_context_batch(
            db, "COMISARIAS", date(2026, 6, 27),
        )
        assert len(result) == 0, "June batch with cutoff Jul 5 excluded for Jun 27 query"

    def test_batch_created_after_period_end_excluded(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 5))

        db = _mock_db_sql([jun])
        result = SiscCifrasService._latest_approved_context_batch(
            db, "COMISARIAS", date(2026, 6, 27),
        )
        assert len(result) == 0, "Batch created Jul 5 excluded for Jun 27 query"

    def test_unapproved_batch_excluded(self):
        batch = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                       status="PENDING", created=datetime(2026, 6, 28))

        db = _mock_db_sql([batch])
        result = SiscCifrasService._latest_approved_context_batch(
            db, "COMISARIAS", date(2026, 7, 27),
        )
        assert len(result) == 0, "PENDING batch should be excluded"

    def test_oldest_valid_batch_is_selected(self):
        jun_v1 = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                        version=1, created=datetime(2026, 6, 28))
        jun_v2 = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                        version=2, created=datetime(2026, 6, 30))

        db = _mock_db_sql([jun_v1, jun_v2])
        result = SiscCifrasService._latest_approved_context_batch(
            db, "COMISARIAS", date(2026, 7, 27),
        )
        assert len(result) == 1
        assert result[0].version == 2


class TestContextCoverageType:

    def test_exact_has_priority_over_context(self):
        jul = _batch("COMISARIAS", "E1", "2026-07", date(2026, 7, 31),
                     created=datetime(2026, 8, 1),
                     indicators=[_ind("VIIF", 40)])
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [jul]

        exact = SiscCifrasService.family_indicators(
            db, date(2026, 7, 1), date(2026, 7, 31),
            date(2025, 7, 1), date(2025, 7, 31), edition_type="monthly",
        )
        assert len(exact) >= 1, "Monthly period should produce EXACT indicators"
        assert exact[0].metadata.get("coverage_type") == "EXACT"

    def test_context_coverage_type_label(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 20)])
        with _with_context([jun]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert all(ind.metadata.get("coverage_type") == "CONTEXT" for ind in context)

    def test_context_has_no_comparison_value(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 20)])
        with _with_context([jun]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert all(ind.comparison_value is None for ind in context)

    def test_exact_has_comparison_value(self):
        jul = _batch("COMISARIAS", "E1", "2026-07", date(2026, 7, 31),
                     created=datetime(2026, 8, 1),
                     indicators=[_ind("VIIF", 40)])
        prev = _batch("COMISARIAS", "E1", "2025-07", date(2025, 7, 31),
                      created=datetime(2025, 8, 1),
                      indicators=[_ind("VIIF", 35)])
        db = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [jul, prev]

        exact = SiscCifrasService.family_indicators(
            db, date(2026, 7, 1), date(2026, 7, 31),
            date(2025, 7, 1), date(2025, 7, 31), edition_type="monthly",
        )
        assert len(exact) >= 1
        assert exact[0].comparison_value is not None

    def test_suppression_preserves_indicators_with_null_value(self):
        tiny = _ind("VIIF", 3, privacy_threshold=10)
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 6, 30), indicators=[tiny])
        with _with_context([jun]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert len(context) == 1, "Suppressed indicators should still be returned"
        assert context[0].value is None
        assert context[0].metadata.get("privacy_threshold_applied") is True

    def test_non_public_indicators_filtered(self):
        private = _ind("VIIF", 20, is_public=False)
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1), indicators=[private])
        with _with_context([jun]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert len(context) == 0, "Non-public indicators should be filtered"


class TestContextMultiEntity:

    def test_multi_entity_different_months(self):
        e1 = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 20)])
        e2 = _batch("COMISARIAS", "E2", "2026-05", date(2026, 5, 31),
                     created=datetime(2026, 6, 1),
                     indicators=[_ind("VIIF", 15)])
        with _with_context([e1, e2]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert len(context) >= 1, "Context should include data from multiple entities"

    def test_entity_normalization(self):
        jun = _batch("COMISARIAS", " COMISARIA PRIMERA ", "2026-06",
                     date(2026, 6, 30), created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 20)])
        with _with_context([jun]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert len(context) == 1
        assert "COMISARIA PRIMERA" in context[0].indicator_code

    def test_duplicate_entity_uses_latest_version(self):
        old = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     version=1, created=datetime(2026, 6, 28),
                     indicators=[_ind("VIIF", 10)])
        new = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     version=2, created=datetime(2026, 6, 30),
                     indicators=[_ind("VIIF", 20)])
        with _with_context([old, new]):
            context = SiscCifrasService.family_context_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                edition_type="weekly",
            )
        assert len(context) == 1
        assert context[0].value == 20.0


class TestContextCollectIndicators:

    def test_collect_indicators_falls_back_to_context(self):
        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 25)])
        with _with_context([jun]):
            indicators = SiscCifrasService.collect_indicators(
                MagicMock(), date(2026, 7, 21), date(2026, 7, 27),
                date(2025, 7, 21), date(2025, 7, 27),
                ["COMISARIAS_FAMILIA"], edition_type="weekly",
            )
        family = [i for i in indicators if i.source_code == "COMISARIAS_FAMILIA"]
        assert len(family) >= 1, "collect_indicators should fall back to context"
        assert family[0].metadata.get("coverage_type") == "CONTEXT"

    def test_exact_prevents_context_fallback(self):
        jul = _batch("COMISARIAS", "E1", "2026-07", date(2026, 7, 31),
                     created=datetime(2026, 8, 1),
                     indicators=[_ind("VIIF", 40)])
        db = _mock_db_sql([jul])

        jun = _batch("COMISARIAS", "E1", "2026-06", date(2026, 6, 30),
                     created=datetime(2026, 7, 1),
                     indicators=[_ind("VIIF", 25)])
        with _with_context([jun]):
            indicators = SiscCifrasService.collect_indicators(
                db, date(2026, 7, 1), date(2026, 7, 31),
                date(2025, 7, 1), date(2025, 7, 31),
                ["COMISARIAS_FAMILIA"], edition_type="monthly",
            )
        family = [i for i in indicators if i.source_code == "COMISARIAS_FAMILIA"]
        assert family[0].metadata.get("coverage_type") == "EXACT"


class TestContextPDF:

    def test_pdf_generation_with_context_indicators(self):
        from services.sisc_cifras_pdf import build_sisc_cifras_pdf
        publication = {
            "edition_type": "weekly",
            "period": {"start": "2026-07-21", "end": "2026-07-27"},
            "comparison_period": {"start": "2025-07-21", "end": "2025-07-27"},
            "comparison_label": "mismo periodo del ano anterior",
            "comparison_mode": "year_over_year",
            "generated_at": "2026-07-28T10:00:00Z",
            "indicators": [
                {
                    "id": "ctx-1",
                    "source": "Comisarias de Familia",
                    "source_code": "COMISARIAS_FAMILIA",
                    "domain": "FAMILIA Y PROTECCION",
                    "category": "Familia",
                    "indicator_code": "familia.viif",
                    "indicator_name": "Atenciones por VIIF",
                    "value": 25.0,
                    "unit": "casos",
                    "period_start": "2026-06-01",
                    "period_end": "2026-06-30",
                    "comparison_value": None,
                    "variation_absolute": None,
                    "variation_percentage": None,
                    "quality_status": "VALIDADO",
                    "cutoff_date": "2026-06-30",
                    "metadata": {
                        "period": "2026-06",
                        "coverage_type": "CONTEXT",
                        "reporting_entity": "Comisaria Central",
                        "reporting_basis": "CUMULATIVE",
                    },
                },
            ],
            "insights": [],
            "slides": [],
            "sources": [],
            "governance": {
                "public_only": True,
                "human_review_required": True,
                "publication_ready": True,
                "review_blockers": [],
                "context_warnings": ["Cobertura contextual"],
                "privacy_note": "Solo indicadores publicos",
                "aggregation_note": "Dominios separados",
            },
        }
        pdf_bytes = build_sisc_cifras_pdf(publication)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


class TestContextSchemaContract:

    def test_explore_result_accepts_context_fields(self):
        from schemas.bulletin_responses import ExploreResult
        result = ExploreResult(
            key="test",
            label="Test",
            domain="ATENCIONES_COMISARIA",
            source_code="COMISARIAS_FAMILIA",
            unit="ATENCIONES",
            is_suppressed=False,
            count=25,
            comparison_count=None,
            percentage_change=None,
            coverage_type="CONTEXT",
            source_period="2026-06",
            cutoff_date=date(2026, 6, 30),
            context_label="Corte mensual 2026-06",
            reporting_entity="Comisaria Central",
            reporting_basis="CUMULATIVE",
        )
        assert result.coverage_type == "CONTEXT"
        assert result.source_period == "2026-06"

    def test_explore_result_context_requires_fields(self):
        from schemas.bulletin_responses import ExploreResult
        with pytest.raises(Exception):
            ExploreResult(
                key="test",
                label="Test",
                domain="ATENCIONES_COMISARIA",
                source_code="COMISARIAS_FAMILIA",
                unit="ATENCIONES",
                is_suppressed=False,
                count=25,
                comparison_count=None,
                percentage_change=None,
                coverage_type="CONTEXT",
            )

    def test_explore_result_context_nulls_comparisons(self):
        from schemas.bulletin_responses import ExploreResult
        with pytest.raises(Exception):
            ExploreResult(
                key="test",
                label="Test",
                domain="ATENCIONES_COMISARIA",
                source_code="COMISARIAS_FAMILIA",
                unit="ATENCIONES",
                is_suppressed=False,
                count=25,
                comparison_count=10,
                percentage_change=50.0,
                coverage_type="CONTEXT",
                source_period="2026-06",
                cutoff_date=date(2026, 6, 30),
                context_label="Corte mensual 2026-06",
                reporting_entity="Comisaria Central",
                reporting_basis="CUMULATIVE",
            )

    def test_explore_result_exact_allows_comparisons(self):
        from schemas.bulletin_responses import ExploreResult
        result = ExploreResult(
            key="test",
            label="Test",
            domain="ATENCIONES_COMISARIA",
            source_code="COMISARIAS_FAMILIA",
            unit="ATENCIONES",
            is_suppressed=False,
            count=25,
            comparison_count=20,
            percentage_change=25.0,
            coverage_type="EXACT",
        )
        assert result.comparison_count == 20
        assert result.percentage_change == 25.0
