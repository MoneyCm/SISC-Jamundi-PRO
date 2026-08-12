import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api import dq, ingesta, inspecciones, institutional_indicators, intelligence
from api.auth import SecurityChecker, get_optional_user, institutional_access
from core.config import DEFAULT_CORS_ORIGINS, get_cors_origins


def _request(api_key=None):
    headers = []
    if api_key is not None:
        headers.append((b"x-api-key", api_key.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/intelligence/reports/trigger",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def _user(*roles):
    return SimpleNamespace(roles=[SimpleNamespace(code=role) for role in roles])


def test_cors_defaults_are_explicit_and_wildcard_is_rejected():
    assert get_cors_origins("") == list(DEFAULT_CORS_ORIGINS)
    assert get_cors_origins("https://uno.test/, https://uno.test, https://dos.test") == [
        "https://uno.test",
        "https://dos.test",
    ]
    with pytest.raises(RuntimeError):
        get_cors_origins("*")


def test_report_trigger_fails_closed_without_service_key(monkeypatch):
    monkeypatch.delenv("SISC_REPORT_TRIGGER_KEY", raising=False)
    with pytest.raises(HTTPException) as error:
        intelligence._authorize_report_trigger(_request(), None)
    assert error.value.status_code == 503


def test_report_trigger_rejects_wrong_service_key(monkeypatch):
    monkeypatch.setenv("SISC_REPORT_TRIGGER_KEY", "correct-service-key-" + "x" * 32)
    with pytest.raises(HTTPException) as error:
        intelligence._authorize_report_trigger(_request("wrong-service-key-" + "y" * 32), None)
    assert error.value.status_code == 403


def test_report_trigger_accepts_service_key_or_authorized_user(monkeypatch):
    service_key = "correct-service-key-" + "x" * 32
    monkeypatch.setenv("SISC_REPORT_TRIGGER_KEY", service_key)
    assert intelligence._authorize_report_trigger(_request(service_key), None) == "SERVICE"

    monkeypatch.delenv("SISC_REPORT_TRIGGER_KEY", raising=False)
    assert intelligence._authorize_report_trigger(_request(), _user("ANALYST")) == "USER"


def test_report_trigger_rejects_placeholder_service_key(monkeypatch):
    monkeypatch.setenv("SISC_REPORT_TRIGGER_KEY", "replace_with_different_random_service_key")
    with pytest.raises(HTTPException) as error:
        intelligence._authorize_report_trigger(
            _request("replace_with_different_random_service_key"),
            None,
        )
    assert error.value.status_code == 503


def test_optional_session_ignores_tokens_in_query_parameters():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/download",
            "headers": [],
            "query_string": b"token=jwt-in-url",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )
    db = MagicMock()

    assert asyncio.run(get_optional_user(request, db)) is None
    db.query.assert_not_called()


def test_internal_intelligence_routes_require_institutional_access():
    protected_paths = {
        "/executive-brief",
        "/stats/compare",
        "/stats/ytd",
        "/stats/accumulated",
        "/rnmc/medidas/backlog",
        "/rnmc/medidas/history",
        "/reports/history",
        "/reports/{report_run_id}",
        "/ingest/status/{log_id}",
        "/stats",
        "/municipios",
        "/years",
    }

    for path in protected_paths:
        routes = [route for route in intelligence.router.routes if route.path == path]
        assert routes, f"No existe la ruta esperada {path}"
        assert all(
            any(dependency.call is institutional_access for dependency in route.dependant.dependencies)
            for route in routes
        ), f"La ruta {path} no exige acceso institucional"


def _role_guard(router, path):
    route = next(route for route in router.routes if route.path == path)
    return next(
        dependency.call
        for dependency in route.dependant.dependencies
        if isinstance(dependency.call, SecurityChecker)
    )


def test_operational_modules_enforce_the_roles_shown_in_navigation():
    dq_guard = _role_guard(dq.router, "/run")
    assert set(dq_guard.allowed_roles) == {"STEWARD", "FUNC_ADMIN", "TI_ADMIN"}

    upload_guard = _role_guard(inspecciones.router, "/upload")
    assert set(upload_guard.allowed_roles) == {"ANALYST", "DIRECTIVE", "FUNC_ADMIN", "TI_ADMIN"}
    expedientes_route = next(route for route in inspecciones.router.routes if route.path == "/expedientes")
    assert any(dependency.call is institutional_access for dependency in expedientes_route.dependant.dependencies)

    operations_guard = _role_guard(institutional_indicators.router, "/agent-ingest")
    assert "SOURCE_UPLOADER" in operations_guard.allowed_roles
    approval_guard = _role_guard(institutional_indicators.router, "/batches/{batch_id}/approve")
    assert "DATA_OWNER" in approval_guard.allowed_roles
    assert "SOURCE_UPLOADER" not in approval_guard.allowed_roles

    clear_guard = _role_guard(ingesta.router, "/clear")
    assert clear_guard.allowed_roles == ["TI_ADMIN"]


def test_mass_delete_requires_exact_confirmation():
    db = MagicMock()
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ingesta.clear_all_events(
                _request(),
                "CONFIRMAR",
                db,
                SimpleNamespace(id="admin-1"),
            )
        )

    assert error.value.status_code == 400
    db.query.assert_not_called()
