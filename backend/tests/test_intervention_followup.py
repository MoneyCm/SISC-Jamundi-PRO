"""Intervenciones nacidas de compromisos y su seguimiento a 30/60/90 días. Deshace todo al final."""
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api import interventions
from api.auth import get_current_user
from db.models import get_db
from db.models_council import CouncilCommitment
from db.session import engine
from services import intervention_followup as followup


def test_small_base_reports_cases_not_percentage():
    assert followup.describe_change(4, 10) == {"before": 4, "after": 10, "difference": 6,
                                               "variation_pct": None, "small_base": True}
    assert followup.describe_change(40, 30)["variation_pct"] == -25.0


def test_windows_are_equal_and_adjacent():
    plan = followup.window_plan(date(2026, 5, 1), 30)
    assert plan["before_end"] == plan["after_start"] - timedelta(days=1)
    assert plan["before_end"] - plan["before_start"] == plan["after_end"] - plan["after_start"]


def test_alert_indicator_only_when_municipal():
    doc = {"alert_snapshot": {"entity_ref": {"indicator": "HOMICIDIO", "territory": "JAMUNDI"}}}
    assert followup.case_indicator(doc) == "HOMICIDIO"
    doc["alert_snapshot"]["entity_ref"]["territory"] = "BARRIO X"
    assert followup.case_indicator(doc) is None
    assert followup.case_indicator({**doc, "indicator": "HURTO_MOTOS"}) == "HURTO_MOTOS"


def test_origin_must_be_exactly_one():
    doc = {"problem": "p", "assessment": "a"}
    with pytest.raises(ValidationError):
        interventions.CreateCase(document=doc)
    with pytest.raises(ValidationError):
        interventions.CreateCase(alert_id=uuid4(), commitment_code="CS-1", document=doc)
    with pytest.raises(ValidationError):
        interventions.CaseDocument(**doc, indicator="POLICIA_REGISTROS")  # diagnóstico, no seguimiento


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


def test_commitment_intervention_with_followup(db):
    run = followup.latest_covering_run(db)
    if not run:
        pytest.skip("Sin entrega policial con cobertura en la base local.")
    code = f"CS-TEST-{uuid4().hex[:6].upper()}"
    db.add(CouncilCommitment(code=code, text="Controles en la vía a Potrerito", responsible="Policía", status="PENDIENTE"))
    db.commit()
    app = FastAPI()
    app.include_router(interventions.router, prefix="/api/interventions")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid4(), username="prueba", data_level_max=3, roles=[SimpleNamespace(code="DIRECTIVE")])
    client = TestClient(app)

    created = client.post("/api/interventions/", json={"commitment_code": code.lower(), "document": {
        "problem": "Hurto de motos en la vía", "assessment": "Crece desde abril", "indicator": "HURTO_MOTOS"}})
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["commitment_code"] == code and case["document"]["commitment_snapshot"]["responsible"] == "Policía"
    assert client.get("/api/interventions/by-commitment").json()[code] == ["BORRADOR"]
    assert client.get(f"/api/interventions/{case['id']}/followup").json()["status"] == "SIN_INICIO"

    # Inicio 100 días antes del corte de datos: las tres ventanas se pueden medir.
    started = run.cobertura_fin - timedelta(days=100)
    document = {**case["document"], "recommendation": "Puesto de control", "decision": "Aprobado en Consejo",
                "responsible": "Policía", "decision_date": started.isoformat(), "deadline": run.cobertura_fin.isoformat(),
                "intervention": "Puesto de control fines de semana", "started_on": started.isoformat(),
                "status": "DECIDIDA"}
    document.pop("commitment_snapshot")
    updated = client.put(f"/api/interventions/{case['id']}", json={"expected_version": 0, "document": document})
    assert updated.status_code == 200, updated.text
    assert updated.json()["document"]["commitment_snapshot"]["code"] == code  # el origen no se pierde

    result = client.get(f"/api/interventions/{case['id']}/followup").json()
    assert result["status"] == "OK" and result["indicator"] == "HURTO_MOTOS"
    assert [w["days"] for w in result["windows"]] == [30, 60, 90]
    for window in result["windows"]:
        assert window["status"] in {"MEDIDO", "SIN_BASE"}
        if window["status"] == "MEDIDO" and window["before"] < followup.SMALL_BASE:
            assert window["variation_pct"] is None


def test_recent_start_is_pending(db):
    result = followup.followup(db, {"indicator": "HOMICIDIO", "started_on": (date.today() - timedelta(days=10)).isoformat()})
    if result["status"] == "SIN_DATOS":
        pytest.skip("Sin entrega policial con cobertura en la base local.")
    assert {w["status"] for w in result["windows"]} == {"PENDIENTE"}
