"""Reglas y recorrido transaccional del expediente; live solo en staging explícito."""
import os
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api import interventions as api


def document(status="BORRADOR"):
    return dict(problem="Concentración de hechos", assessment="Análisis descriptivo", recommendation="Controles",
        decision="Acta de prueba", responsible="Secretaría", decision_date="2026-06-28", deadline="2026-07-01",
        intervention="Controles registrados", started_on="2026-06-29", completed_on="2026-06-30",
        evidence=[{"description": "Acta", "url": "https://example.org/acta"}], status=status)


def evaluation(**changes):
    return api.Evaluation(**(dict(expected_version=3, source_version_id=uuid4(), methodology_version="1",
        before_start="2026-06-22", before_end="2026-06-28", after_start="2026-07-01", after_end="2026-07-07",
        assessment="No se establece causalidad") | changes))


@pytest.mark.parametrize("changes", [
    {"problem": " "}, {"status": "DECIDIDA", "responsible": ""},
    {"deadline": "2026-06-01"}, {"started_on": "2026-06-01"},
    {"completed_on": "2026-06-01"}, {"status": "EN_EJECUCION", "intervention": ""},
    {"status": "FINALIZADA", "evidence": []},
    {"evidence": [{"description": "script", "url": "javascript:alert(1)"}]},
    {"evaluation": {"value": 999}},
])
def test_invalid_document(changes):
    with pytest.raises(ValidationError):
        api.CaseDocument(**(document() | changes))


@pytest.mark.parametrize("changes", [
    {"after_end": "2026-07-08"}, {"after_start": "2026-06-28", "after_end": "2026-07-04"},
    {"before_start": "2026-06-29"},
])
def test_invalid_periods(changes):
    with pytest.raises(ValidationError):
        evaluation(**changes)


def case_row():
    return SimpleNamespace(status="FINALIZADA", document=document("FINALIZADA") | {
        "alert_snapshot": {"entity_ref": {"indicator": "HOMICIDIO", "territory": "JAMUNDI"}}})


def db_with_run(**changes):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(**(dict(
        id=uuid4(), status="COMPLETED", fuente_codigo="POLICIA_SEMANAL",
        cobertura_inicio=date(2026, 6, 22), cobertura_fin=date(2026, 7, 7)) | changes))
    return db


@pytest.mark.parametrize("changes", [{"cobertura_inicio": None}, {"cobertura_fin": date(2026, 7, 6)}, {"status": "FAILED"}])
def test_missing_coverage_never_zero(changes):
    with pytest.raises(HTTPException) as exc:
        api.comparison(db_with_run(**changes), case_row(), evaluation())
    assert exc.value.status_code == 422


def test_periods_must_bracket_execution():
    row = case_row()
    row.document["completed_on"] = "2026-07-02"
    with pytest.raises(HTTPException):
        api.comparison(db_with_run(), row, evaluation())


@pytest.mark.parametrize("before,after,pct", [(0, 2, None), (12, 7, -41.67)])
def test_fixed_source_and_no_causal_claim(before, after, pct):
    with patch.object(api, "calculate_indicator", side_effect=[{"value": before}, {"value": after}]) as calc:
        result = api.comparison(db_with_run(), case_row(), evaluation())
    assert result["variation_pct"] == pct
    assert result["difference"] == after - before
    assert "no demuestra" in result["note"]
    assert calc.call_args_list[0].kwargs["source_version_id"] == calc.call_args_list[1].kwargs["source_version_id"]


def test_stale_version():
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = SimpleNamespace(version=2)
    with pytest.raises(HTTPException) as exc:
        api.load_case(db, uuid4(), 1)
    assert exc.value.status_code == 409


def test_live_staging_lifecycle():
    """Actual PostgreSQL, rolled back; explicit URL required, never production."""
    url = os.environ.get("INTERVENTIONS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configure INTERVENTIONS_TEST_DATABASE_URL para PostgreSQL staging")
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"} and parsed.database == "sisc_staging"
    from db.models_alerts import IntelligenceAlert
    from db.models_interventions import InterventionCase, InterventionRevision
    engine = create_engine(url)
    # Schema supplied by the migration; test never creates/changes production schema.
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        alert = IntelligenceAlert(id=uuid4(), source="SISC_WEEKLY", alert_type="WEEKLY_HOMICIDIO", severity="HIGH",
            title="Prueba expediente", body_md="Prueba", entity_ref={"indicator": "HOMICIDIO", "territory": "JAMUNDI"},
            metrics={"current_value": 1}, dedupe_key=str(uuid4()))
        session.add(alert)
        session.commit()
        app = FastAPI()
        app.include_router(api.router, prefix="/interventions")
        app.dependency_overrides[api.get_db] = lambda: session
        actor = SimpleNamespace(username="analista_expediente", id=uuid4())
        app.dependency_overrides[api.analyst_or_admin] = lambda: actor
        app.dependency_overrides[api.institutional_access] = lambda: actor
        try:
            with TestClient(app) as client:
                r = client.post("/interventions/", json={"alert_id": str(alert.id), "document": document()})
                assert r.status_code == 201, r.text
                case_id = r.json()["id"]
                for version, status in enumerate(["DECIDIDA", "EN_EJECUCION", "FINALIZADA"]):
                    r = client.put(f"/interventions/{case_id}", json={"expected_version": version, "document": document(status)})
                    assert r.status_code == 200, r.text
                r = client.put(f"/interventions/{case_id}", json={"expected_version": 0, "document": document()})
                assert r.status_code == 409
                history = client.get(f"/interventions/{case_id}").json()
                assert len(history["revisions"]) == 4
                assert history["revisions"][0]["document"]["status"] == "BORRADOR"
                assert all(r["username"] == actor.username for r in history["revisions"])
                assert history["document"]["alert_snapshot"]["evidence"] == {"current_value": 1}
                # Real rows and snapshot calculation for the comparison.
                from db.models_hechos_seguridad import IngestionRun, SabanaSnapshotRow
                run = IngestionRun(id=uuid4(), fuente_codigo="POLICIA_SEMANAL", filename="interventions-test",
                    hash_archivo=str(uuid4()), status="COMPLETED", cobertura_inicio=date(2026, 6, 22), cobertura_fin=date(2026, 7, 7))
                session.add(run)
                session.flush()
                for n, day in enumerate([date(2026, 6, 23), date(2026, 6, 24), date(2026, 7, 2)]):
                    session.add(SabanaSnapshotRow(ingestion_id=run.id, record_key=f"test-{n}", hecho_key=f"ID:{n}",
                        fecha_evento=day, conducta_estandar="HOMICIDIO", anio=2026, datos_normalizados={}))
                session.commit()
                request = evaluation(source_version_id=run.id).model_dump(mode="json")
                r = client.post(f"/interventions/{case_id}/evaluate", json=request)
                assert r.status_code == 200, r.text
                result = r.json()["document"]["evaluation"]
                assert result["before"]["value"] == 2 and result["after"]["value"] == 1
                assert result["variation_pct"] == -50
                assert client.put(f"/interventions/{case_id}", json={"expected_version": 4, "document": document("FINALIZADA")}).status_code == 422
                actor.username = "segundo_analista"
                assert len(client.get(f"/interventions/{case_id}").json()["revisions"]) == 5
                assert client.get("/interventions/", params={"alert_id": str(alert.id)}).json()["items"][0]["status"] == "EVALUADA"
                def citizen():
                    raise HTTPException(403, "Rol insuficiente")
                app.dependency_overrides[api.analyst_or_admin] = citizen
                assert client.post("/interventions/", json={"alert_id": str(alert.id), "document": document()}).status_code == 403
        finally:
            session.close()
            transaction.rollback()
    engine.dispose()
