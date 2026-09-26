"""Estudios completos (tope, pausa, campo, revisión) y memoria institucional. Deshace todo al final."""
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
import db.models_alerts  # noqa: F401  (tabla referenciada por intervention_cases)
from db.models_interventions import InterventionCase
from db.models_observatory import ObservatoryRecommendation, ObservatoryStudy
from db.session import engine
from services import institutional_memory as memory
from services import observatory_service


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        # Estudios abiertos de la base local no deben contar para el tope de esta prueba.
        session.query(ObservatoryStudy).filter(ObservatoryStudy.status.in_(("ABIERTO", "EN_CURSO"))).update(
            {ObservatoryStudy.status: "PAUSADO", ObservatoryStudy.status_note: "prueba"})
        session.flush()
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def client(db, *roles):
    app = FastAPI()
    app.include_router(observatory.router, prefix="/api/observatory")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba.memoria", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def study(title, **extra):
    return {"title": title, "question": "¿Qué explica el aumento de este fenómeno en el territorio?", **extra}


def test_open_study_limit_and_pause(db):
    api = client(db, "ANALYST")
    first = api.post("/api/observatory/studies", json=study("Estudio uno")).json()
    api.post("/api/observatory/studies", json=study("Estudio dos"))
    third = api.post("/api/observatory/studies", json=study("Estudio tres"))
    assert third.status_code == 409 and "tope" in third.json()["detail"]
    fields = {key: first[key] for key in ("title", "question", "phenomenon", "territory", "period_start", "period_end",
                                          "sources", "hypotheses", "findings", "access_level")}
    no_reason = api.put(f"/api/observatory/studies/{first['id']}", json={**fields, "status": "PAUSADO", "expected_version": 0})
    assert no_reason.status_code == 422
    paused = api.put(f"/api/observatory/studies/{first['id']}",
                     json={**fields, "status": "PAUSADO", "status_note": "Llegó un pedido urgente", "expected_version": 0})
    assert paused.status_code == 200 and paused.json()["status_note"] == "Llegó un pedido urgente"
    assert api.post("/api/observatory/studies", json=study("Estudio tres")).status_code == 201
    reopen = api.put(f"/api/observatory/studies/{first['id']}", json={**fields, "status": "EN_CURSO", "expected_version": 1})
    assert reopen.status_code == 409


def test_field_notes_and_review_signal(db):
    api = client(db, "ANALYST")
    created = api.post("/api/observatory/studies", json=study("Estudio con campo")).json()
    base = f"/api/observatory/studies/{created['id']}/field-notes"
    assert api.post(base, json={"kind": "CHARLA", "on_date": "2026-09-20", "summary": "Resumen suficientemente largo"}).status_code == 422
    note = api.post(base, json={"kind": "RECORRIDO", "on_date": "2026-09-20", "place": "Potrerito",
                                "participants": "líder comunal", "summary": "Se observan puntos sin iluminación."}).json()
    assert len(api.get(f"/api/observatory/studies/{created['id']}").json()["field_notes"]) == 1
    assert api.delete(f"{base}/{note['id']}").status_code == 204
    assert api.delete(f"{base}/{note['id']}").status_code == 404

    row = db.get(ObservatoryStudy, created["id"])
    row.review_on = date(2031, 3, 1)
    db.flush()
    titles = [item["title"] for item in observatory_service.knowledge_signals(db, date(2031, 3, 5), True)]
    assert f"Toca la revisión posterior del estudio {row.code}" in titles


def test_memory_collects_closed_work(db):
    closed = ObservatoryStudy(code=f"OBS-T-{uuid4().hex[:6]}", title="Hurto de motos en la galería", question="¿Por qué crece?",
                              territory="Centro", findings="Concentración en horas de la noche.", status="CERRADO",
                              associated_factors="Parqueo informal", created_by="prueba")
    hidden = ObservatoryStudy(code=f"OBS-T-{uuid4().hex[:6]}", title="Estudio reservado", question="¿Por qué crece?",
                              findings="Reservado.", status="CERRADO", access_level="RESERVADO", created_by="prueba")
    db.add_all([closed, hidden])
    db.flush()
    db.add(ObservatoryRecommendation(code=f"REC-T-{uuid4().hex[:6]}", study_id=closed.id, title="Iluminar la galería",
                                     text="Instalar luminarias en el parqueadero.", status="RECHAZADA",
                                     decision_note="Sin presupuesto este año", decided_on=date(2031, 2, 1), created_by="prueba"))
    db.add(InterventionCase(status="FINALIZADA", commitment_code=f"CS-T-{uuid4().hex[:4]}", document={
        "problem": "Hurtos en la galería", "intervention": "Patrullaje nocturno", "completed_on": "2031-01-31"}))
    db.flush()

    everything = memory.build_memory(db, include_reserved=True)
    codes = {item["code"] for item in everything["items"]}
    assert closed.code in codes and hidden.code in codes
    public = memory.build_memory(db, include_reserved=False)
    assert hidden.code not in {item["code"] for item in public["items"]}

    found = memory.build_memory(db, include_reserved=False, q="GALERÍA presupuesto")
    assert [item["kind"] for item in found["items"]] == ["RECOMENDACION"]
    assert found["items"][0]["outcome"] == "Rechazada: Sin presupuesto este año"
    study_item = next(item for item in public["items"] if item["code"] == closed.code)
    assert study_item["outcome"] == "1 recomendaciones, 0 adoptadas"
    intervention = next(item for item in public["items"] if item["kind"] == "INTERVENCION" and item["summary"] == "Hurtos en la galería")
    assert intervention["outcome"] == "Finalizada sin evaluar" and intervention["date"] == "2031-01-31"
    assert memory.build_memory(db, include_reserved=False, kind="ESTUDIO", year=1999)["items"] == []
    assert memory.export_csv(found).lstrip("﻿").splitlines()[0].startswith("Tipo;Código;Fecha")


def test_memory_api(db):
    api = client(db, "ANALYST")
    assert api.get("/api/observatory/memory?kind=OTRO").status_code == 422
    assert api.get("/api/observatory/memory").status_code == 200
    export = api.get("/api/observatory/memory/export")
    assert export.status_code == 200 and "memoria_observatorio.csv" in export.headers["content-disposition"]
