"""Humo del guard tri-fuente tras cablear identidad SPOA/ML.

Verifica que `require_tri_fuente_homicidios` (publication_guards.py) acepta la
publicación cuando `source_version_ids` trae los 3 snapshots fijos
(POLICIA_SEMANAL, FISCALIA_SPOA_V3, MEDICINA_LEGAL) y revierte con 422 cuando
falta alguna entrega fija.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

SPOA_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ML_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
POLICIA_UUID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _row():
    row = MagicMock()
    row.source_codes = ["POLICIA_SEMANAL", "FISCALIA_SPOA_V3", "MEDICINA_LEGAL"]
    row.source_version_ids = {
        "POLICIA_SEMANAL": POLICIA_UUID,
        "FISCALIA_SPOA_V3": SPOA_UUID,
        "MEDICINA_LEGAL": ML_UUID,
    }
    row.period_start = "2025-01-01"
    row.period_end = "2025-12-31"
    return row


def test_tri_fuente_ok_with_all_snapshots(monkeypatch):
    from services import publication_guards

    fake_reconcile = MagicMock(return_value={"fuente_final": "FISCALIA_SPOA_V3"})
    monkeypatch.setattr(
        "services.reconciliation_tri_fuente_service.reconcile_homicidios_tri_fuente",
        fake_reconcile,
    )
    db = MagicMock()
    result = publication_guards.require_tri_fuente_homicidios(db, _row())
    assert result == {"fuente_final": "FISCALIA_SPOA_V3"}
    fake_reconcile.assert_called_once()
    kwargs = fake_reconcile.call_args.kwargs
    assert kwargs["source_version_ids"] == _row().source_version_ids


def test_tri_fuente_422_when_ml_missing(monkeypatch):
    from services import publication_guards

    row = _row()
    del row.source_version_ids["MEDICINA_LEGAL"]
    db = MagicMock()
    with pytest.raises(HTTPException) as e:
        publication_guards.require_tri_fuente_homicidios(db, row)
    assert e.value.status_code == 422
    assert "MEDICINA_LEGAL" in e.value.detail


def test_tri_fuente_noop_without_spoa_or_ml(monkeypatch):
    from services import publication_guards

    row = MagicMock()
    row.source_codes = ["INSPECCIONES_RNMC"]
    row.source_version_ids = {}
    db = MagicMock()
    assert publication_guards.require_tri_fuente_homicidios(db, row) == {}
