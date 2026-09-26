"""Solicitudes de datos: estados por periodicidad, API y avisos de la portada. Deshace todo al final."""
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
from db.models_data_requests import DataEntity, DataRequest
from db.session import engine
from services import data_requests as dr

TODAY = date(2031, 3, 17)  # lunes, lejos de datos reales


def req(status="PEDIDA", requested=TODAY - timedelta(days=2), due=TODAY + timedelta(days=1), received=None):
    return SimpleNamespace(status=status, requested_on=requested, due_on=due, received_on=received)


def test_match_key_ignores_accents_and_generic_words():
    assert dr.match_key("Inspección Tercera de Policía") == dr.match_key("Inspeccion Tercera") == "INSPECCION TERCERA"
    assert dr.match_key("Comisaría Segunda de Familia") == "COMISARIA SEGUNDA"


def test_states_by_cadence():
    assert dr.entity_state("SEMANAL", [], TODAY)["state"] == "TOCA_PEDIR"
    assert dr.entity_state("SEMANAL", [req()], TODAY)["state"] == "ESPERANDO"
    late = dr.entity_state("SEMANAL", [req(requested=TODAY - timedelta(days=8), due=TODAY - timedelta(days=5))], TODAY)
    assert (late["state"], late["days_late"], late["days_waiting"]) == ("ATRASADA", 5, 8)
    answered = req("RECIBIDA", received=TODAY - timedelta(days=9))
    assert dr.entity_state("SEMANAL", [answered], TODAY)["state"] == "AL_DIA"  # 7 + 3 días de gracia
    old = req("RECIBIDA", received=TODAY - timedelta(days=11))
    assert dr.entity_state("SEMANAL", [old], TODAY)["state"] == "TOCA_PEDIR"
    assert dr.entity_state("MENSUAL", [old], TODAY)["state"] == "AL_DIA"
    # "Sin respuesta" cierra la solicitud pero no cuenta como respuesta.
    assert dr.entity_state("SEMANAL", [req("SIN_RESPUESTA")], TODAY)["state"] == "TOCA_PEDIR"


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


def entity(db, name, cadence="SEMANAL"):
    row = DataEntity(name=name, program="INSPECCIONES", cadence=cadence)
    db.add(row)
    db.flush()
    return row


def test_portada_titles(db):
    db.query(DataEntity).update({DataEntity.active: False})  # solo las de la prueba
    silent = entity(db, "Inspección Prueba Uno")
    db.add(DataRequest(entity_id=silent.id, what="Semana", requested_on=TODAY - timedelta(days=25),
                       due_on=TODAY - timedelta(days=22), created_by="prueba"))
    known = entity(db, "Comisaría Prueba Dos")
    db.add_all([
        DataRequest(entity_id=known.id, what="Semana", requested_on=TODAY - timedelta(days=30), due_on=TODAY - timedelta(days=27),
                    status="RECIBIDA", received_on=TODAY - timedelta(days=21), created_by="prueba"),
        DataRequest(entity_id=known.id, what="Semana", requested_on=TODAY - timedelta(days=7), due_on=TODAY - timedelta(days=4),
                    created_by="prueba"),
    ])
    entity(db, "Inspección Prueba Tres")
    db.flush()
    rows = dr.signals(db, TODAY)
    titles = [row["title"] for row in rows]
    assert "Comisaría Prueba Dos sin reportar hace 3 semanas" in titles
    assert f"Inspección Prueba Uno no ha respondido la solicitud del {TODAY - timedelta(days=25):%d/%m}" in titles
    assert next(row for row in rows if row["title"].startswith("Inspección Prueba Uno"))["level"] == "ALTA"
    assert rows[-1]["title"] == "Toca pedir datos a 1 dependencia"


def client(db, *roles):
    app = FastAPI()
    app.include_router(observatory.router, prefix="/api/observatory")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba.datos", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_api_flow(db):
    api = client(db, "ANALYST")
    created = api.post("/api/observatory/data-entities", json={"name": "Inspección Prueba API", "program": "INSPECCIONES", "cadence": "SEMANAL"})
    assert created.status_code == 201
    assert api.post("/api/observatory/data-entities", json={"name": "inspección prueba api"}).status_code == 409
    assert api.post("/api/observatory/data-entities", json={"name": "Otra prueba", "cadence": "DIARIA"}).status_code == 422
    entity_id = created.json()["id"]

    body = {"entity_ids": [entity_id], "what": "Reporte semanal", "requested_on": "2031-03-17"}
    [request] = api.post("/api/observatory/data-requests", json=body).json()
    assert request["due_on"] == "2031-03-20" and request["status"] == "PEDIDA"
    assert api.post("/api/observatory/data-requests", json={**body, "due_on": "2031-03-10"}).status_code == 422
    assert api.post("/api/observatory/data-requests", json={**body, "entity_ids": [str(uuid4())]}).status_code == 404

    url = f"/api/observatory/data-requests/{request['id']}"
    assert api.put(url, json={"status": "RECIBIDA", "received_on": "2031-03-01", "expected_version": 0}).status_code == 422
    done = api.put(url, json={"status": "RECIBIDA", "received_on": "2031-03-18", "expected_version": 0})
    assert done.status_code == 200 and done.json()["received_on"] == "2031-03-18"
    assert api.put(url, json={"status": "PEDIDA", "expected_version": 0}).status_code == 409
    reopened = api.put(url, json={"status": "PEDIDA", "received_on": "2031-03-18", "expected_version": 1}).json()
    assert reopened["received_on"] is None

    board = api.get("/api/observatory/data-requests").json()
    assert any(row["name"] == "Inspección Prueba API" for row in board["entities"])
    assert client(db, "CITIZEN").get("/api/observatory/data-requests").status_code == 403
