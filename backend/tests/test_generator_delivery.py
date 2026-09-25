"""The simplified generator cannot silently switch upload or publication period."""
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.sisc_cifras import GenerateSiscCifrasRequest, _check_selected_delivery


@pytest.mark.parametrize("fault", ["latest", "row", "period"])
def test_changed_delivery_or_period_blocked(fault):
    source = uuid4()
    payload = GenerateSiscCifrasRequest(source_version_id=source, period_start=date(2026, 7, 1), period_end=date(2026, 7, 5))
    row = SimpleNamespace(source_version_ids={"POLICIA_SEMANAL": str(uuid4() if fault == "row" else source)},
        period_start=payload.period_start, period_end=date(2026, 7, 4) if fault == "period" else payload.period_end)
    with patch('services.publication_guards.require_fixed_delivery'), patch('services.indicator_calculation._latest_completed_run', return_value=SimpleNamespace(id=uuid4() if fault == "latest" else source)):
        with pytest.raises(HTTPException) as exc:
            _check_selected_delivery(MagicMock(), payload, row)
        assert exc.value.status_code == (422 if fault == "period" else 409)


def test_matching_delivery_passes():
    source = uuid4()
    payload = GenerateSiscCifrasRequest(source_version_id=source, period_start=date(2026, 7, 1), period_end=date(2026, 7, 5))
    row = SimpleNamespace(source_version_ids={"POLICIA_SEMANAL": str(source)}, period_start=payload.period_start, period_end=payload.period_end)
    with patch('services.publication_guards.require_fixed_delivery'), patch('services.indicator_calculation._latest_completed_run', return_value=SimpleNamespace(id=source)):
        _check_selected_delivery(MagicMock(), payload, row)
