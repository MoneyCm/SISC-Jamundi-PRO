"""Guardas de publicación + negativas de aceptación."""
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from unittest.mock import MagicMock
from fastapi import HTTPException
import pytest


def _run(status="COMPLETED"):
    r = MagicMock()
    r.status = status
    r.id = "11111111-1111-1111-1111-111111111111"
    return r


def _db_with_run(run=None, total=2, hom=1):
    from services import publication_guards as g
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = run
    # calculate_indicator usa db.query(...).filter(...).scalar() y max(fecha); simplificamos parcheando la función
    return db


def test_reject_publish_without_fixed_delivery():
    from services.publication_guards import require_fixed_delivery
    db = MagicMock()
    with pytest.raises(HTTPException) as e:
        require_fixed_delivery(db, None)
    assert e.value.status_code == 422
    assert "entrega fija" in e.value.detail


def test_reject_unusable_delivery():
    from services.publication_guards import require_fixed_delivery
    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.first.return_value = _run(status="FAILED")
    with pytest.raises(HTTPException) as e:
        require_fixed_delivery(db, "11111111-1111-1111-1111-111111111111")
    assert "no es utilizable" in e.value.detail


def test_reject_bad_methodology():
    from services.publication_guards import require_methodology
    with pytest.raises(HTTPException) as e:
        require_methodology("0")
    assert "no ejecutable" in e.value.detail
    with pytest.raises(HTTPException):
        require_methodology(None)


def test_verify_rejects_local_mismatch(monkeypatch):
    from services import publication_guards as g
    def fake_calc(db, **kw):
        code = kw.get("indicator")
        return {"value": 2 if code == "SEGURIDAD_TOTAL" else 1}
    monkeypatch.setattr(g, "calculate_indicator", fake_calc)
    db = MagicMock()
    with pytest.raises(HTTPException) as e:
        g.verify_official_figures(db, period_start=date(2026, 7, 1), period_end=date(2026, 7, 12),
                                  source_version_id="11111111-1111-1111-1111-111111111111",
                                  methodology_version="1",
                                  expected={"SEGURIDAD_TOTAL": 99})
    assert "no coincide" in e.value.detail


def test_enforce_requires_versions_on_row():
    from services import publication_guards as g
    db = MagicMock()
    row = MagicMock()
    row.methodology_version = None
    row.period_start = date(2026, 7, 1)
    row.period_end = date(2026, 7, 12)
    row.source_version_ids = {}
    row.source_codes = ["POLICIA_SEMANAL"]
    row.publication_json = {"indicators": []}
    with pytest.raises(HTTPException):
        g.enforce_publication_integrity(db, row)
