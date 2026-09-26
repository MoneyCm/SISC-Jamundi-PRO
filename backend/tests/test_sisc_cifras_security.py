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


def _publish_setup(monkeypatch, checks):
    """Boletín institucional publicando directo, con la revisión editorial simulada."""
    from uuid import uuid4
    import services.publication_guards as guards
    import services.publication_review as review_module

    publication_id = str(uuid4())
    generate = MagicMock(return_value={"id": publication_id, "status": "DRAFT", "governance": {"history_saved": True}})
    monkeypatch.setattr(sisc_cifras.SiscCifrasService, "generate_publication", generate)
    monkeypatch.setattr(sisc_cifras, "log_audit", AsyncMock())
    monkeypatch.setattr(review_module, "review_publication", lambda publication: checks)
    monkeypatch.setattr(guards, "enforce_publication_integrity", lambda db, row: {"ok": True})
    row = SimpleNamespace(id=publication_id, status="DRAFT", edition_type="weekly",
                          period_start=date(2026, 9, 6), period_end=date(2026, 9, 12), publication_json={})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    db.query.return_value.filter.return_value.all.return_value = []
    return db, row


def _publish(db, acknowledged=False):
    return asyncio.run(sisc_cifras.generate_sisc_cifras(
        sisc_cifras.GenerateSiscCifrasRequest(save_history=True, publish_automatically=True,
                                             warnings_acknowledged=acknowledged),
        _request(), db, _user("ANALYST"),
    ))


def test_bulletin_with_blocking_review_is_not_published(monkeypatch):
    db, row = _publish_setup(monkeypatch, [{"code": "SEMANA_PRELIMINAR", "level": "BLOQUEA", "title": "Semana preliminar", "detail": "x"}])
    with pytest.raises(HTTPException) as error:
        _publish(db)
    assert error.value.status_code == 422
    assert "No se publicó" in error.value.detail and "Semana preliminar" in error.value.detail
    assert row.status == "DRAFT"


def test_bulletin_warnings_must_be_acknowledged(monkeypatch):
    checks = [{"code": "BASE_PEQUENA", "level": "REVISAR", "title": "Base pequeña", "detail": "x"}]
    db, row = _publish_setup(monkeypatch, checks)
    with pytest.raises(HTTPException) as error:
        _publish(db, acknowledged=False)
    assert "Confirme" in error.value.detail and row.status == "DRAFT"

    result = _publish(db, acknowledged=True)
    assert result["status"] == "PUBLISHED" and row.status == "PUBLISHED"
    approval = result["governance"]["approval"]
    assert approval["approved_by"] == "analista"
    assert approval["warnings_acknowledged"] == ["BASE_PEQUENA"]
    assert approval["channel"] == "BOLETIN_INSTITUCIONAL"
    assert result["governance"]["automatic_publication"] is False
