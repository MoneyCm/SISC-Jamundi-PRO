"""Cierre: PDF desde publicación guardada, importador estricto, metodología explícita."""
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock


def _mock_db_for_indicator(value=54):
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.scalar.side_effect = [value, __import__("datetime").date(2026, 7, 12)]
    q.first.return_value = None
    return db


def test_pdf_uses_saved_publication_not_current():
    # La publicación A conserva sus cifras aunque exista B: el endpoint filtra por id.
    import inspect
    from api import sisc_cifras as mod
    src = inspect.getsource(mod.get_public_sisc_cifras_pdf)
    assert "publication_id" in src
    assert "publication_json" in src
    assert "pdf_sha256" in src  # integridad del archivo distinguida del contenido estadístico


def test_importer_requires_recalculation_match():
    import inspect
    from api import sisc_cifras as mod
    src = inspect.getsource(mod.import_legacy_bulletin)
    assert "no coincide con lo declarado" in src
    assert "CIFRAS_DECLARADAS" in src
    assert "409" in src  # duplicados


def test_old_methodology_is_explicit_error():
    from services.indicator_calculation import calculate_indicator
    db = _mock_db_for_indicator()
    try:
        calculate_indicator(db, indicator="HOMICIDIO", period_start="2026-01-01",
                            period_end="2026-07-12", methodology_version="0")
    except ValueError as exc:
        assert "no ejecutable" in str(exc)
    else:
        raise AssertionError("debió fallar con metodología antigua")


def test_exploratory_is_not_publishable():
    from services.indicator_calculation import calculate_indicator
    db = _mock_db_for_indicator()
    r = calculate_indicator(db, indicator="SEGURIDAD_TOTAL", period_start="2026-01-01", period_end="2026-07-12")
    assert r["exploratory"] is True and r["reproducible"] is False
    assert "fije source_version_id" in r["publication_note"]
