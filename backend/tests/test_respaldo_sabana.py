"""Respaldo cuando la sábana de la Policía no llega."""
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from db.session import engine
from services import respaldo_sabana as rs
from tests.test_hoja_ejecutiva import datos_ejemplo
from services import hoja_ejecutiva as hoja


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


def test_sin_alerta_si_la_sabana_es_reciente(db, monkeypatch):
    monkeypatch.setattr(rs, "_corte_sabana", lambda db: date(2026, 9, 12))
    e = rs.estado(db, hoy=date(2026, 9, 28))
    assert e["dias_retraso"] == 16 and not e["atrasada"] and e["respaldo"] == []


def test_alerta_y_respaldo_cuando_mindefensa_es_mas_reciente(db, monkeypatch):
    monkeypatch.setattr(rs, "_corte_sabana", lambda db: date(2026, 7, 4))
    monkeypatch.setattr(rs, "_cifras_mindefensa", lambda db: {
        "corte": date(2026, 8, 31), "filas": [{"delito": "Homicidios", "actual": 79, "anterior": 86}]})
    e = rs.estado(db, hoy=date(2026, 9, 28))
    assert e["atrasada"] and e["respaldo_disponible"] and e["respaldo_corte"] == "2026-08-31"
    assert e["respaldo"][0]["actual"] == 79


def test_alerta_sin_respaldo_si_mindefensa_no_es_mas_reciente(db, monkeypatch):
    monkeypatch.setattr(rs, "_corte_sabana", lambda db: date(2026, 9, 12))
    monkeypatch.setattr(rs, "_cifras_mindefensa", lambda db: {"corte": date(2026, 8, 31), "filas": [{"delito": "x", "actual": 1, "anterior": 1}]})
    e = rs.estado(db, hoy=date(2026, 9, 12) + timedelta(days=30))
    assert e["atrasada"] and not e["respaldo_disponible"] and e["respaldo"] == []


def test_cifras_de_mindefensa_de_la_base(db):
    cifras = rs._cifras_mindefensa(db)
    if cifras["corte"] is None:
        pytest.skip("Sin referencia de MinDefensa en esta base")
    assert [f["delito"] for f in cifras["filas"]][:2] == ["Homicidios", "Lesiones personales"]
    assert all(f["actual"] >= 0 and f["anterior"] >= 0 for f in cifras["filas"])


def test_la_hoja_con_respaldo_sigue_en_una_pagina():
    datos = datos_ejemplo(respaldo={"atrasada": True, "respaldo_disponible": True, "respaldo_corte": "2026-08-31",
                                    "respaldo": [{"delito": d, "actual": 10, "anterior": 12} for d, _ in rs.DELITOS]})
    pdf = hoja.render_pdf(datos)
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 1
