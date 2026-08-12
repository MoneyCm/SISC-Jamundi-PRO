from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from api import source_center
from api.auth import SecurityChecker, institutional_access
from services.source_center_service import SOURCE_CONNECTORS, freshness_status, overall_status


def _request(service_key=None):
    headers = []
    if service_key is not None:
        headers.append((b"x-sisc-source-key", service_key.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/source-center/heartbeat",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        }
    )


def _user(*roles):
    return SimpleNamespace(roles=[SimpleNamespace(code=role) for role in roles])


def test_catalog_has_the_five_distinct_source_connectors():
    assert set(SOURCE_CONNECTORS) == {
        "POLICIA_JAMUNDI",
        "POLICIA_NACIONAL",
        "MINDEFENSA",
        "SIEDCO_PUBLICO",
        "OBSERVATORIO_VALLE",
    }
    assert SOURCE_CONNECTORS["POLICIA_JAMUNDI"]["purpose"] == "Fuente operativa principal"
    assert SOURCE_CONNECTORS["MINDEFENSA"]["purpose"] == "Contraste institucional"
    assert SOURCE_CONNECTORS["SIEDCO_PUBLICO"]["purpose"] == "Contraste estadistico"


def test_freshness_thresholds_are_explicit():
    today = date.today()
    assert freshness_status(today - timedelta(days=14), 14, 35) == "CURRENT"
    assert freshness_status(today - timedelta(days=15), 14, 35) == "LAGGED"
    assert freshness_status(today - timedelta(days=35), 14, 35) == "LAGGED"
    assert freshness_status(today - timedelta(days=36), 14, 35) == "EXPIRED"
    assert freshness_status(None, 14, 35) == "NO_CUTOFF"


def test_overall_status_never_calls_a_source_current_without_cutoff_or_review():
    checked = datetime.now(timezone.utc)
    assert overall_status(
        connected=True,
        monitor_status="CURRENT",
        freshness="NO_CUTOFF",
        last_checked_at=checked,
    ) == "NEEDS_REVIEW"
    assert overall_status(
        connected=True,
        monitor_status="CURRENT",
        freshness="EXPIRED",
        last_checked_at=checked,
    ) == "EXPIRED"
    assert overall_status(
        connected=True,
        monitor_status="UPDATE_AVAILABLE",
        freshness="EXPIRED",
        last_checked_at=checked,
    ) == "UPDATE_AVAILABLE"


def test_heartbeat_fails_closed_without_a_strong_service_key(monkeypatch):
    monkeypatch.delenv("SISC_SOURCE_MONITOR_KEY", raising=False)
    with pytest.raises(HTTPException) as error:
        source_center._authorize_heartbeat(_request(), None)
    assert error.value.status_code == 503

    monkeypatch.setenv("SISC_SOURCE_MONITOR_KEY", "replace_with_another_random_service_key")
    with pytest.raises(HTTPException) as placeholder_error:
        source_center._authorize_heartbeat(
            _request("replace_with_another_random_service_key"),
            None,
        )
    assert placeholder_error.value.status_code == 503


def test_heartbeat_accepts_service_key_or_authorized_operator(monkeypatch):
    service_key = "source-monitor-key-" + "x" * 40
    monkeypatch.setenv("SISC_SOURCE_MONITOR_KEY", service_key)
    assert source_center._authorize_heartbeat(_request(service_key), None) == "SERVICE"

    monkeypatch.delenv("SISC_SOURCE_MONITOR_KEY", raising=False)
    assert source_center._authorize_heartbeat(_request(), _user("STEWARD")) == "USER"


def test_heartbeat_rejects_oversized_monitor_metadata():
    base = {
        "connector_code": "SIEDCO_PUBLICO",
        "last_checked_at": datetime.now(timezone.utc),
    }
    with pytest.raises(ValidationError):
        source_center.SourceHeartbeat(**base, warnings=["x" * 501])
    with pytest.raises(ValidationError):
        source_center.SourceHeartbeat(**base, details={"raw": "x" * 20_001})


def test_source_center_routes_enforce_read_and_operation_permissions():
    summary_route = next(route for route in source_center.router.routes if route.path == "")
    assert any(dependency.call is institutional_access for dependency in summary_route.dependant.dependencies)

    check_route = next(
        route for route in source_center.router.routes if route.path == "/check/{connector_code}"
    )
    guard = next(
        dependency.call
        for dependency in check_route.dependant.dependencies
        if isinstance(dependency.call, SecurityChecker)
    )
    assert set(guard.allowed_roles) == set(source_center.SOURCE_OPERATION_ROLES)
