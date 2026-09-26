"""Plan de acción del PISCC: catálogo, seguimiento semestral, API y avisos. Deshace todo al final."""
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
from db.models_piscc import PisccActionReport
from db.session import engine
from services import piscc_actions as pa


def test_catalog_has_the_43_actions_of_the_plan():
    catalog = pa.load_catalog()
    counts = {}
    for action in catalog["actions"]:
        counts[action["vector"]] = counts.get(action["vector"], 0) + 1
        assert action["goal"] > 0 and action["action"] and action["indicator"]
    assert counts == {"I": 10, "II": 6, "III": 18, "IV": 9}
    codes = [action["code"] for action in catalog["actions"]]
    assert len(set(codes)) == 43 and codes[0] == "I-01" and codes[-1] == "IV-09"


def test_semester_helpers():
    assert pa.semester_of(date(2026, 6, 30)) == "2026-1"
    assert pa.semester_of(date(2026, 7, 1)) == "2026-2"
    assert pa.previous_semester("2026-1") == "2025-2"
    assert pa.previous_semester("2026-2") == "2026-1"
    assert pa.plan_semesters()[0] == "2024-1" and pa.plan_semesters()[-1] == "2027-2"
    assert pa.lead_entity("AMSO – Secretaría de Seguridad y Convivencia") == "AMSO"
    assert pa.progress_pct(30, 24) == 100.0 and pa.progress_pct(6, 24) == 25.0 and pa.progress_pct(None, 4) is None


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


def report(db, code, semester, value, status="EN_EJECUCION"):
    db.add(PisccActionReport(action_code=code, semester=semester, value=value, status=status, created_by="prueba"))
    db.flush()


def test_tracking_carries_last_report_without_counting_it(db):
    report(db, "I-01", "2026-1", 6)
    report(db, "I-01", "2026-2", 12)
    report(db, "II-03", "2026-1", 1, "CUMPLIDA")
    tracking = pa.build_tracking(db, "2026-2")
    actions = {action["code"]: action for action in tracking["actions"]}
    assert actions["I-01"]["reported"] and actions["I-01"]["progress_pct"] == 50.0
    assert not actions["II-03"]["reported"]
    assert actions["II-03"]["last_report"]["semester"] == "2026-1" and actions["II-03"]["progress_pct"] == 100.0
    assert tracking["totals"]["reported"] == 1 and tracking["totals"]["completed"] == 1
    vector_ii = next(vector for vector in tracking["vectors"] if vector["code"] == "II")
    assert vector_ii["average_progress"] == round(100 / 6, 1)
    pending = {item["entity"]: item["actions"] for item in tracking["pending_by_entity"]}
    assert "I-01" not in sum(pending.values(), []) and "II-03" in pending["Secretaría de Seguridad y Convivencia"]
    # Un semestre anterior no ve reportes posteriores.
    assert {a["code"]: a for a in pa.build_tracking(db, "2026-1")["actions"]}["I-01"]["report"]["value"] == 6


def test_csv_for_sispt(db):
    report(db, "I-01", "2026-2", 12.5)
    text = pa.export_csv(pa.build_tracking(db, "2026-2"))
    lines = text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Código;Vector;Responsable") and len(lines) == 44
    assert lines[1].split(";")[7] == "12,5" and lines[1].split(";")[10] == "Sí"


def test_signals_by_month(db):
    assert pa.signals(db, date(2026, 9, 25)) == []
    [may] = pa.signals(db, date(2027, 5, 10))
    assert may["level"] == "MEDIA" and "43 acciones sin reporte" in may["title"]
    [january] = pa.signals(db, date(2027, 1, 10))
    assert january["level"] == "ALTA" and "2026-2" in january["title"]


def client(db, *roles):
    app = FastAPI()
    app.include_router(observatory.router, prefix="/api/observatory")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba.piscc", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_api_saves_reports_with_version_check(db):
    api = client(db, "ANALYST")
    body = {"value": 3, "status": "EN_EJECUCION", "reporting_entity": "AMSO", "evidence": "Oficio 123"}
    first = api.put("/api/observatory/piscc-actions/IV-05/2026-2", json=body)
    assert first.status_code == 200 and first.json()["version"] == 0
    assert api.put("/api/observatory/piscc-actions/IV-05/2026-2", json=body).status_code == 409  # sin versión: ya existe
    second = api.put("/api/observatory/piscc-actions/IV-05/2026-2", json={**body, "value": 4, "expected_version": 0})
    assert second.status_code == 200 and second.json()["value"] == 4 and second.json()["version"] == 1
    assert api.put("/api/observatory/piscc-actions/IV-05/2026-2", json={**body, "expected_version": 0}).status_code == 409
    assert api.put("/api/observatory/piscc-actions/X-99/2026-2", json=body).status_code == 404
    assert api.put("/api/observatory/piscc-actions/IV-05/2030-1", json=body).status_code == 422
    assert api.put("/api/observatory/piscc-actions/IV-05/2026-2", json={**body, "status": "OTRO", "expected_version": 1}).status_code == 422
    listing = api.get("/api/observatory/piscc-actions?semester=2026-2").json()
    assert listing["totals"]["reported"] == 1
    export = api.get("/api/observatory/piscc-actions/export?semester=2026-2")
    assert export.status_code == 200 and "PISCC_seguimiento_2026-2.csv" in export.headers["content-disposition"]


def test_only_analysis_roles_write(db):
    assert client(db, "CITIZEN").put("/api/observatory/piscc-actions/IV-05/2026-2", json={"value": 1}).status_code == 403
