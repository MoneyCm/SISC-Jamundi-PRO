"""Calendario operativo: fecha del Consejo, tareas previas y posteriores, y API. Deshace todo al final."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import observatory
from api.auth import get_current_user
from db.models import get_db
from db.session import engine
from services import operating_calendar as oc


def test_session_date_priority():
    estimated = oc.plan_session(2031, 10, [], [])
    assert (estimated.start, estimated.end, estimated.source) == (date(2031, 10, 25), date(2031, 10, 31), "ESTIMADA")
    assert oc.plan_session(2031, 10, [], [date(2031, 10, 16)]).source == "ACTA"
    registered = oc.plan_session(2031, 10, [date(2031, 10, 28)], [date(2031, 10, 16)])
    assert (registered.start, registered.source) == (date(2031, 10, 28), "REGISTRADA")
    assert oc.plan_session(2032, 2, [], []).start == date(2032, 2, 23)  # bisiesto: 29 - 6


def test_previous_and_upcoming():
    previous, upcoming = oc.sessions_around(date(2031, 10, 10), [], [])
    assert (previous.month, upcoming.month) == (9, 10)
    previous, upcoming = oc.sessions_around(date(2031, 10, 20), [], [date(2031, 10, 16)])
    assert (previous.month, upcoming.month) == (10, 11)  # la de octubre ya pasó (acta del 16)


def test_council_tasks_by_date():
    previous, upcoming = oc.sessions_around(date(2031, 10, 10), [date(2031, 10, 28)], [])
    early = {row["key"]: row for row in oc.council_items(date(2031, 10, 10), previous, upcoming, 2, False, True)}
    assert early["consejo-recomendaciones"]["status"] == "PROXIMO"  # desde el 18
    assert early["consejo-informe"]["status"] == "PROXIMO"
    close = {row["key"]: row for row in oc.council_items(date(2031, 10, 25), previous, upcoming, 2, False, True)}
    assert close["consejo-recomendaciones"]["status"] == "PENDIENTE"
    assert close["consejo-informe"]["status"] == "PENDIENTE" and "en 3 días" in close["consejo-informe"]["detail"]
    done = {row["key"]: row for row in oc.council_items(date(2031, 10, 25), previous, upcoming, 0, True, True)}
    assert done["consejo-recomendaciones"]["status"] == done["consejo-informe"]["status"] == "HECHO"


def test_act_is_late_three_days_after():
    previous, upcoming = oc.sessions_around(date(2031, 11, 2), [date(2031, 10, 28)], [])
    rows = {row["key"]: row for row in oc.council_items(date(2031, 11, 2), previous, upcoming, 0, False, False)}
    assert rows["consejo-acta"]["status"] == "ATRASADO" and "octubre" in rows["consejo-acta"]["title"]
    rows = {row["key"]: row for row in oc.council_items(date(2031, 10, 30), previous, upcoming, 0, False, False)}
    assert rows["consejo-acta"]["status"] == "PENDIENTE"


def test_when_text():
    estimated = oc.plan_session(2031, 10, [], [])
    assert oc.when_text(date(2031, 10, 27), estimated) == "esta semana"
    assert oc.when_text(date(2031, 10, 21), estimated) == "en 4 días"


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
    user = SimpleNamespace(id=uuid4(), username="prueba.calendario", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_api_sets_one_session_per_month(db):
    api = client(db, "ANALYST")
    created = api.post("/api/observatory/council-sessions", json={"session_date": "2031-10-28"})
    assert created.status_code == 201
    assert api.post("/api/observatory/council-sessions", json={"session_date": "2031-10-30"}).status_code == 409
    assert api.delete(f"/api/observatory/council-sessions/{created.json()['id']}").status_code == 204
    assert api.post("/api/observatory/council-sessions", json={"session_date": "2031-10-30"}).status_code == 201
    calendar = api.get("/api/observatory/calendar").json()
    assert {"week", "council", "items"} <= set(calendar)
    assert client(db, "CITIZEN").get("/api/observatory/calendar").status_code == 403
