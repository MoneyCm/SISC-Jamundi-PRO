"""Ficha territorial: reglas de cifras, cruce de compromisos y acceso interno. Deshace todo al final."""
from collections import namedtuple
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import observatory
from api.auth import get_current_user
from db.models import get_db
from db.models_council import CouncilCommitment
from db.session import engine
from services import territory_profile as profile

Event = namedtuple("Event", "fecha conducta")


def test_commitment_territory_text_is_split():
    assert profile._parts("Potrerito, Robles") == ["Potrerito", "Robles"]
    assert profile._parts("El Rodeo y La Marina") == ["El Rodeo", "La Marina"]
    assert profile._parts(None) == []


def test_facts_use_small_base_and_same_window():
    cutoff = date(2026, 9, 12)
    events = [{"fecha": date(2026, 3, 1), "conducta": "HOMICIDIO"}] * 5 + [{"fecha": date(2025, 3, 1), "conducta": "HOMICIDIO"}] * 2
    events += [{"fecha": date(2025, 10, 1), "conducta": "HOMICIDIO"}]  # fuera de la ventana del año anterior
    facts = profile.facts_block(events, cutoff)
    assert facts["total"] == {"current": 5, "previous": 2, "difference": 3, "small_base": True, "variation_pct": None}
    assert len(facts["monthly"]) == 12 and facts["monthly"][-1]["partial"]


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def client(db, *roles):
    app = FastAPI()
    app.include_router(observatory.router, prefix="/api/observatory")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid4(), username="prueba", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    return TestClient(app)


def test_profile_links_commitments_and_is_internal(db):
    display, _, _ = profile.resolve("Potrerito")
    if not display:
        pytest.skip("Cartografía local sin Potrerito.")
    code = f"CS-TEST-{uuid4().hex[:6].upper()}"
    db.add(CouncilCommitment(code=code, text="Controles en la vía", territory="Robles, Potrerito", status="PENDIENTE"))
    db.commit()
    analyst = client(db, "ANALYST")
    data = analyst.get("/api/observatory/territories/profile", params={"name": "potrerito"})
    assert data.status_code == 200, data.text
    body = data.json()
    assert body["name"] == display and code in [item["code"] for item in body["decisions"]["commitments"]]
    assert analyst.get("/api/observatory/territories/profile", params={"name": "Lugar Inventado 123"}).status_code == 404
    assert client(db, "VIEWER").get("/api/observatory/territories/profile", params={"name": "Potrerito"}).status_code == 403
    names = [item["name"] for item in analyst.get("/api/observatory/territories").json()]
    assert names == sorted(names, key=profile.GeocodingService.normalize_name)  # alfabético, no ranking
