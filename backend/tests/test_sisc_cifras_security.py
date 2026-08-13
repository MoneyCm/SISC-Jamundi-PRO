import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api import sisc_cifras


def _request(headers=None):
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/sisc-cifras/generate",
            "headers": raw_headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def _user(*roles):
    return SimpleNamespace(
        id="user-1",
        username="analista",
        roles=[SimpleNamespace(code=role) for role in roles],
    )


def test_public_generation_is_preview_only_by_default(monkeypatch):
    generate = MagicMock(return_value={"id": "preview", "governance": {"history_saved": False}})
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "generate_publication", generate)

    result = asyncio.run(
        sisc_cifras.generate_sisc_cifras(
            sisc_cifras.GenerateSiscCifrasRequest(),
            _request(),
            MagicMock(),
            None,
        )
    )

    assert result["governance"]["history_saved"] is False
    assert generate.call_args.kwargs["save_history"] is False
    assert generate.call_args.kwargs["created_by"] is None


def test_operational_summary_is_public_read_only(monkeypatch):
    expected = {
        "period": {"start": "2026-07-01", "end": "2026-07-31"},
        "governance": {"public_only": True},
    }
    summary = MagicMock(return_value=expected)
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "operational_summary", summary)

    result = sisc_cifras.get_operational_summary(
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        comparison_mode="previous_year",
        db=MagicMock(),
    )

    assert result == expected
    summary.assert_called_once()


def test_anonymous_user_cannot_save_publication(monkeypatch):
    generate = MagicMock()
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "generate_publication", generate)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            sisc_cifras.generate_sisc_cifras(
                sisc_cifras.GenerateSiscCifrasRequest(save_history=True),
                _request(),
                MagicMock(),
                None,
            )
        )

    assert error.value.status_code == 401
    generate.assert_not_called()


def test_unapproved_role_cannot_save_publication(monkeypatch):
    generate = MagicMock()
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "generate_publication", generate)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            sisc_cifras.generate_sisc_cifras(
                sisc_cifras.GenerateSiscCifrasRequest(save_history=True),
                _request(),
                MagicMock(),
                _user("CITIZEN"),
            )
        )

    assert error.value.status_code == 403
    generate.assert_not_called()


def test_analyst_can_save_audited_publication(monkeypatch):
    generate = MagicMock(return_value={"id": "draft-1", "governance": {"history_saved": True}})
    audit = AsyncMock()
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "generate_publication", generate)
    monkeypatch.setattr(sisc_cifras, "log_audit", audit)

    result = asyncio.run(
        sisc_cifras.generate_sisc_cifras(
            sisc_cifras.GenerateSiscCifrasRequest(save_history=True),
            _request(),
            MagicMock(),
            _user("ANALYST"),
        )
    )

    assert result["id"] == "draft-1"
    assert generate.call_args.kwargs["save_history"] is True
    assert generate.call_args.kwargs["created_by"] == "analista"
    audit.assert_awaited_once()
