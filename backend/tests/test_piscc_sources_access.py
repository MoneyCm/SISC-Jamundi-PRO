"""Quién puede leer las metas del PISCC que usa el Boletín institucional."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import piscc_sources
from api.auth import get_current_user
from db.session import get_db


def client(monkeypatch, *roles):
    monkeypatch.setattr(piscc_sources, "get_piscc_sources", lambda db, cutoff: {"sources": []})
    monkeypatch.setattr(piscc_sources, "build_goals", lambda db, cutoff, version: [])
    app = FastAPI()
    app.include_router(piscc_sources.router, prefix="/api/sisc-cifras/piscc-sources")
    app.dependency_overrides[get_db] = lambda: None
    user = SimpleNamespace(id=uuid4(), username="prueba", data_level_max=2, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize("role", ["SOURCE_UPLOADER", "DIRECTIVE", "ANALYST", "STEWARD"])
def test_bulletin_roles_can_read_piscc_goals(monkeypatch, role):
    response = client(monkeypatch, role).get("/api/sisc-cifras/piscc-sources?cutoff=2026-08-31")
    assert response.status_code == 200 and response.json()["goals"] == []


def test_other_roles_cannot(monkeypatch):
    assert client(monkeypatch, "PORTAL_EDITOR").get("/api/sisc-cifras/piscc-sources?cutoff=2026-08-31").status_code == 403
