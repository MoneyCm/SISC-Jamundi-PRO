"""El backend publico solo expone las rutas del portal ciudadano."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def public_app(monkeypatch):
    monkeypatch.setenv("SISC_PUBLIC_ONLY", "true")
    monkeypatch.delenv("SISC_PUBLIC_ALLOW_WRITES", raising=False)
    import main
    module = importlib.reload(main)
    yield module.app
    monkeypatch.delenv("SISC_PUBLIC_ONLY")
    importlib.reload(main)


def _paths(app):
    return {(m, r.path) for r in app.router.routes for m in getattr(r, "methods", set())}


def test_public_mode_keeps_only_citizen_routes(public_app):
    paths = _paths(public_app)
    assert ("GET", "/api/analitica/public/dashboard") in paths
    assert ("GET", "/api/analitica/public/piscc") in paths
    for method, path in paths:
        assert not path.startswith(("/api/auth", "/api/ingesta", "/api/users", "/api/source-center",
                                    "/api/alerts-tray", "/api/council-commitments", "/api/narrative-alerts")), path
    assert ("POST", "/api/participacion/reportes-seguros") not in paths
    # Generador de SISC en cifras y archivo de boletines: solo en la oficina.
    assert not any(path.startswith("/api/sisc-cifras") for _, path in paths)


def test_public_mode_hides_login_and_docs(public_app):
    client = TestClient(public_app)
    assert client.post("/api/auth/login", data={"username": "x", "password": "y"}).status_code in (404, 405)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/users/").status_code == 404


def test_public_mode_does_not_expose_protected_routes(public_app):
    from core.public_mode import _requires_auth
    from fastapi.routing import APIRoute
    for route in public_app.router.routes:
        if isinstance(route, APIRoute):
            assert not _requires_auth(route), route.path
