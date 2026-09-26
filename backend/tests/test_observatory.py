"""Centro de Análisis: estudios, recomendaciones y portada. Corre contra la base local y deshace todo al final."""
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
from services import observatory_service


def user(*roles):
    return SimpleNamespace(id=uuid4(), username="prueba.observatorio", data_level_max=3,
                           roles=[SimpleNamespace(code=code) for code in roles])


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


def client(db, current):
    app = FastAPI()
    app.include_router(observatory.router, prefix="/api/observatory")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


STUDY = {"title": "Hurto de vehículos en la vía a Potrerito",
         "question": "¿Por qué crecen los hurtos de vehículos en la vía Jamundí - Potrerito en 2026?",
         "territory": "Vía Jamundí - Potrerito - Río Claro", "sources": ["POLICIA_SEMANAL"]}


def test_study_and_recommendation_flow(db):
    analyst = client(db, user("ANALYST"))
    study = analyst.post("/api/observatory/studies", json=STUDY)
    assert study.status_code == 201, study.text
    study = study.json()
    assert study["code"].startswith(f"OBS-{date.today().year}-")

    # Cerrar sin hallazgos no se permite.
    closed = analyst.put(f"/api/observatory/studies/{study['id']}",
                         json={**STUDY, "status": "CERRADO", "expected_version": 0})
    assert closed.status_code == 422

    rec = analyst.post("/api/observatory/recommendations", json={
        "study_id": study["id"], "title": "Controles en la vía", "text": "Puesto de control los fines de semana.",
        "addressed_to": "Consejo de Seguridad", "priority": "ALTA"}).json()
    assert rec["status"] == "PROPUESTA" and rec["study_code"] == study["code"]

    def move(status, version, **extra):
        return analyst.post(f"/api/observatory/recommendations/{rec['id']}/status",
                            json={"status": status, "expected_version": version, **extra})

    assert move("ACEPTADA", 0, note="x").status_code == 422  # no se acepta sin presentarse
    assert move("PRESENTADA", 0, on_date=(date.today() + timedelta(days=1)).isoformat()).status_code == 422
    assert move("PRESENTADA", 0).status_code == 200
    assert move("ACEPTADA", 1).status_code == 422  # decisión sin nota
    assert move("ACEPTADA", 0, note="Consejo").status_code == 409  # versión vieja
    assert move("ACEPTADA", 1, note="Consejo de Seguridad").status_code == 200
    assert move("EN_EJECUCION", 2).status_code == 422  # sin compromiso enlazado
    assert move("EN_EJECUCION", 2, commitment_code="NO-EXISTE-999").status_code == 422

    code = f"CS-TEST-{uuid4().hex[:6].upper()}"
    db.add(CouncilCommitment(code=code, text="Compromiso de prueba", status="PENDIENTE"))
    db.commit()
    done = move("EN_EJECUCION", 2, commitment_code=code.lower())
    assert done.status_code == 200, done.text
    assert done.json()["commitment_code"] == code
    assert [item["status"] for item in done.json()["history"]] == ["PROPUESTA", "PRESENTADA", "ACEPTADA", "EN_EJECUCION"]


def test_reserved_studies_hidden_from_other_roles(db):
    analyst = client(db, user("ANALYST"))
    reserved = analyst.post("/api/observatory/studies", json={**STUDY, "access_level": "RESERVADO"}).json()
    viewer = client(db, user("VIEWER"))
    assert viewer.get(f"/api/observatory/studies/{reserved['id']}").status_code == 404
    assert reserved["id"] not in {row["id"] for row in viewer.get("/api/observatory/studies").json()}
    assert viewer.post("/api/observatory/studies", json=STUDY).status_code == 403


def test_overview_flags_unanswered_recommendations(db):
    analyst = client(db, user("ANALYST"))
    rec = analyst.post("/api/observatory/recommendations", json={
        "title": "Iluminación", "text": "Iluminar el corredor del parque."}).json()
    old = (date.today() - timedelta(days=40)).isoformat()
    analyst.post(f"/api/observatory/recommendations/{rec['id']}/status",
                 json={"status": "PRESENTADA", "expected_version": 0, "on_date": old})
    signals = observatory_service.knowledge_signals(db, date.today(), include_reserved=True)
    unanswered = next(item for item in signals if item["key"] == "sin-respuesta")
    assert unanswered["level"] == "ALTA" and unanswered["count"] >= 1


def test_overview_never_breaks_when_a_module_fails(db, monkeypatch):
    def broken(*_):
        raise RuntimeError("fuente caída")

    monkeypatch.setattr(observatory_service, "territory_signals", broken)
    monkeypatch.setattr(observatory_service, "source_signals", broken)
    data = observatory_service.overview(db)
    keys = {item["key"] for item in data["signals"]}
    assert "error-radar" in keys and "error-fuentes" in keys
    assert "compromisos" in keys or "sin-informacion" in keys
