"""Informe para decisión del Consejo: contenido, reglas de cifras, PDF y acceso reservado. Deshace todo al final."""
import io
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pypdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import council_commitments
from api.auth import get_current_user
from db.models import get_db
from db.models_council import CouncilCommitment
from db.models_observatory import ObservatoryRecommendation
from db.session import engine
from services import council_decision_report as report
from services.council_decision_report_pdf import _change, build_council_sheet_pdf, build_decision_report_pdf


def test_small_base_is_reported_in_cases():
    assert report.compare(10, 2) == {"current": 10, "previous": 2, "difference": 8, "small_base": True, "variation_pct": None}
    assert report.compare(45, 31)["variation_pct"] == 45.2
    assert _change(report.compare(10, 2)) == "+8 hechos"
    assert _change(report.compare(2, 3)) == "-1 hecho"
    assert _change({"previous": None}) == "sin base"


def test_overdue_come_before_repeated():
    today = date(2026, 9, 30)
    rows = [
        CouncilCommitment(code="A", text="repetido", status="PENDIENTE", mentions=5, instance="CONSEJO_SEGURIDAD"),
        CouncilCommitment(code="B", text="atrasado", status="PENDIENTE", mentions=1, deadline_date=today - timedelta(days=3)),
        CouncilCommitment(code="C", text="al día", status="PENDIENTE", mentions=1, deadline_date=today + timedelta(days=3)),
        CouncilCommitment(code="D", text="cumplido", status="CUMPLIDO", mentions=4),
    ]
    assert [item["code"] for item in report.attention(rows, today)] == ["B", "A"]


def test_last_session_and_overdue_by_owner():
    today = date(2026, 9, 30)
    last = date(2026, 9, 21)
    rows = [
        CouncilCommitment(code="N1", text="nuevo", status="SIN_INFORMACION", origin_date=last, responsible="Policía"),
        CouncilCommitment(code="R1", text="repetido", status="SIN_INFORMACION", origin_date=date(2026, 8, 24), last_mention_date=last),
        CouncilCommitment(code="V1", text="viejo", status="SIN_INFORMACION", origin_date=date(2026, 8, 24)),
        CouncilCommitment(code="D1", text="descartado", status="DESCARTADO", origin_date=last),
        CouncilCommitment(code="A1", text="atrasado", status="SIN_INFORMACION", responsible="Gobierno", deadline_date=date(2026, 4, 8)),
        CouncilCommitment(code="A2", text="atrasado", status="SIN_INFORMACION", responsible="Gobierno", deadline_date=date(2026, 1, 15)),
        CouncilCommitment(code="A3", text="atrasado sin dueño", status="SIN_INFORMACION", deadline_date=date(2026, 6, 1)),
        CouncilCommitment(code="C1", text="cumplido", status="CUMPLIDO", responsible="Gobierno", deadline_date=date(2026, 1, 1)),
    ]
    assert [item["code"] for item in report.last_session_items(rows, last, today)] == ["N1", "R1"]
    assert report.last_session_items(rows, None, today) == []
    groups = report.overdue_by_owner(rows, today)
    assert [(group["responsible"], group["count"]) for group in groups] == [("Gobierno", 2), ("Por definir", 1)]
    assert [item["code"] for item in groups[0]["items"]] == ["A2", "A1"]  # el más antiguo primero


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


def test_pending_recommendation_is_first_decision_and_pdf_fits_two_pages(db):
    db.add(ObservatoryRecommendation(code=f"REC-TEST-{uuid4().hex[:5]}", title="Puesto de control en la vía",
                                     text="Controles fines de semana en la vía a Potrerito.", status="PRESENTADA",
                                     presented_on=date.today(), created_by="prueba"))
    db.commit()
    data = report.build_report(db, "CONSEJO_SEGURIDAD", date.today())
    assert data["decisions"]["items"][0]["kind"] == "RECOMENDACION"
    assert len(data["decisions"]["items"]) <= report.MAX_DECISIONS
    assert report.RESERVED_NOTE in data["notes"]
    pdf = build_decision_report_pdf(data)
    assert len(pypdf.PdfReader(io.BytesIO(pdf)).pages) == 2
    assert len(pdf) < 500_000  # circula por WhatsApp
    sheet = build_council_sheet_pdf(data)
    assert len(pypdf.PdfReader(io.BytesIO(sheet)).pages) == 1


def test_report_is_reserved_to_followup_roles(db):
    app = FastAPI()
    app.include_router(council_commitments.router, prefix="/api/council-commitments")
    app.dependency_overrides[get_db] = lambda: db

    def as_user(*roles):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=uuid4(), username="prueba", data_level_max=3, roles=[SimpleNamespace(code=code) for code in roles])
        return TestClient(app)

    assert as_user("VIEWER").get("/api/council-commitments/decision-report").status_code == 403
    assert as_user("DIRECTIVE").get("/api/council-commitments/decision-report?instance=NO_EXISTE").status_code == 422
    response = as_user("DIRECTIVE").get("/api/council-commitments/decision-report.pdf?session_date=2026-09-30")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert "informe-decision-cs-2026-09-30.pdf" in response.headers["content-disposition"]
    sheet = as_user("DIRECTIVE").get("/api/council-commitments/session-sheet.pdf?session_date=2026-09-30")
    assert sheet.status_code == 200 and sheet.headers["content-type"] == "application/pdf"
    assert "hoja-sesion-cs-2026-09-30.pdf" in sheet.headers["content-disposition"]
    assert as_user("VIEWER").get("/api/council-commitments/session-sheet.pdf").status_code == 403
