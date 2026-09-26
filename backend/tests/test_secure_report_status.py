"""Reportes seguros: estado de atención, notas obligatorias, versión y permisos. Deshace todo al final."""
from datetime import date, time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import participacion
from api.auth import get_current_user
from db.models import SecureReport, get_db
from db.session import engine
from services import monday_brief


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
    app.include_router(participacion.router, prefix="/api/participacion")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba.reportes", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def report(db, anonymous=True):
    row = SecureReport(tipo="HURTO A PERSONAS", barrio="Centro", fecha=date(2026, 9, 1), hora=time(20, 30),
                       descripcion="Me quitaron el celular cerca del parque.", es_anonimo=anonymous,
                       nombre=None if anonymous else "Persona de prueba", contacto=None if anonymous else "300 000 0000")
    db.add(row)
    db.flush()
    return row


def test_new_report_starts_received_and_moves_with_notes(db):
    row = report(db)
    api = client(db, "ANALYST")
    listing = api.get("/api/participacion/admin/reportes-seguros").json()
    item = next(entry for entry in listing["items"] if entry["id"] == str(row.id))
    assert item["estado"] == "RECIBIDO" and item["version"] == 0 and item["contacto"] is None
    url = f"/api/participacion/admin/reportes-seguros/{row.id}/estado"

    assert api.put(url, json={"estado": "CERRADO", "expected_version": 0}).status_code == 422  # cerrar sin nota
    started = api.put(url, json={"estado": "EN_GESTION", "expected_version": 0})
    assert started.status_code == 200 and started.json()["estado"] == "EN_GESTION"
    assert api.put(url, json={"estado": "EN_GESTION", "expected_version": 1}).status_code == 422  # transición inválida
    assert api.put(url, json={"estado": "CERRADO", "nota": "Remitido", "expected_version": 0}).status_code == 409
    closed = api.put(url, json={"estado": "CERRADO", "nota": "Remitido al cuadrante 3 de la Policía", "expected_version": 1}).json()
    assert closed["estado"] == "CERRADO" and [event["a"] for event in closed["gestion"]] == ["EN_GESTION", "CERRADO"]
    assert closed["gestion"][-1]["nota"] == "Remitido al cuadrante 3 de la Policía"
    assert api.put(url, json={"estado": "EN_GESTION", "expected_version": 2}).status_code == 422  # reabrir sin nota
    assert api.put(url, json={"estado": "EN_GESTION", "nota": "La persona volvió a escribir", "expected_version": 2}).status_code == 200


def test_closed_reports_leave_inbox_and_brief(db):
    row = report(db, anonymous=False)
    api = client(db, "ANALYST")
    text = monday_brief.citizen_pending(db)
    assert text and "sin gestión" in text
    url = f"/api/participacion/admin/reportes-seguros/{row.id}/estado"
    api.put(url, json={"estado": "CERRADO", "nota": "Atendido por la comisaría", "expected_version": 0})
    inbox = api.get("/api/participacion/admin/bandeja").json()["items"]
    assert str(row.id) not in {item["id"] for item in inbox}


def test_contact_only_when_not_anonymous(db):
    shown = participacion.serialize_report(report(db, anonymous=False))
    hidden = participacion.serialize_report(report(db, anonymous=True))
    assert shown["contacto"] == "300 000 0000" and hidden["contacto"] is None and hidden["nombre"] is None


def test_only_authorized_roles(db):
    row = report(db)
    assert client(db, "CITIZEN").get("/api/participacion/admin/reportes-seguros").status_code == 403
    assert client(db, "CITIZEN").put(f"/api/participacion/admin/reportes-seguros/{row.id}/estado",
                                     json={"estado": "EN_GESTION", "expected_version": 0}).status_code == 403
    assert client(db, "ANALYST").get("/api/participacion/admin/reportes-seguros?estado=OTRO").status_code == 422
