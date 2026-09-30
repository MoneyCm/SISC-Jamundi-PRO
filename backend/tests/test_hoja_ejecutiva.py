"""Hoja ejecutiva semanal: frases, una sola página y quién puede descargarla."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import reportes
from api.auth import get_current_user
from db.models import get_db
from db.session import engine
from services import hoja_ejecutiva as hoja


def fila(delito, semana, anterior, anio, anio_anterior):
    return {"delito": delito, "semana": semana, "semana_anterior": anterior, "anio": anio,
            "anio_anterior": anio_anterior, "tendencia_semana": hoja.tendencia(semana, anterior),
            "variacion_anio": hoja.variacion(anio, anio_anterior)}


def datos_ejemplo(**cambios):
    filas = [fila("Homicidios", 1, 2, 78, 79), fila("Lesiones personales", 1, 4, 206, 269),
             fila("Hurto a personas", 11, 3, 343, 357), fila("Hurto de motos y carros", 2, 3, 222, 155),
             fila("Hurto a residencias", 3, 0, 59, 61), fila("Hurto a comercio", 0, 0, 41, 51)]
    datos = {
        "corte": date(2026, 9, 12), "hoy": date(2026, 9, 27), "dias_retraso": 15,
        "semana": (date(2026, 9, 6), date(2026, 9, 12)), "semana_anterior": (date(2026, 8, 30), date(2026, 9, 5)),
        "anio": (date(2026, 1, 1), date(2026, 9, 12)), "anio_anterior": (date(2025, 1, 1), date(2025, 9, 12)),
        "filas": filas, "total": fila("Total de delitos", 18, 12, 939, 958),
        "barrios": [{"barrio": "Terranova", "casos": 9, "principal": "Hurto a personas"}],
        "compromisos": {"abiertos": 125, "vencidos": 26, "cumplidos": 8, "atencion": [
            {"codigo": "CS-1", "texto": "Presentar informe mensual " * 12, "responsable": "Policía Nacional",
             "veces": 6, "vencido": True}] * 3},
    }
    datos["frases"] = hoja.frases(filas, datos["total"], datos["barrios"], {"overdue": 26}, 15)
    datos.update(cambios)
    return datos


def test_frases_en_lenguaje_sencillo():
    lineas = datos_ejemplo()["frases"]
    assert lineas[0] == "Se registró 1 homicidio en la semana (2 la semana anterior)."
    assert any("hurto de motos y carros" in l and "+43 %" in l for l in lineas)
    assert any("lesiones personales" in l and "-23 %" in l for l in lineas)
    assert any("26 compromisos" in l for l in lineas)
    assert any("15 días de retraso" in l for l in lineas)


def test_sin_homicidios_y_sin_retraso():
    filas = datos_ejemplo()["filas"]
    filas[0] = fila("Homicidios", 0, 2, 78, 79)
    lineas = hoja.frases(filas, filas[0], [], {"overdue": 0}, 3)
    assert lineas[0] == "No se registraron homicidios en la semana."
    assert not any("retraso" in l or "compromisos" in l for l in lineas)


def test_nombres_de_lugar():
    assert hoja.nombre_lugar("CGTO BOCAS DEL PALO") == "Corregimiento Bocas del Palo"
    assert hoja.nombre_lugar("CIUDADELA TERRANOVA") == "Ciudadela Terranova"
    assert hoja.variacion(5, 0) is None


def test_el_pdf_es_una_sola_pagina_aunque_haya_texto_largo():
    datos = datos_ejemplo()
    datos["frases"] = datos["frases"] + ["Una frase muy larga para forzar el ajuste. " * 8] * 3
    pdf = hoja.render_pdf(datos)
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages") == 1
    assert len(pdf) < 600_000


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


def test_construir_con_la_base(db):
    try:
        datos = hoja.construir(db)
    except ValueError:
        pytest.skip("Sin sábana cargada en esta base")
    assert [f["delito"] for f in datos["filas"]][0] == "Homicidios" and len(datos["filas"]) == 6
    assert datos["semana"][1] == datos["corte"] and (datos["semana"][1] - datos["semana"][0]).days == 6
    # Un hecho puede tener varios delitos (caso real: homicidio y lesiones el 22/09/2026), así que las
    # filas pueden sumar más que el total; pero ninguna fila supera el total de hechos únicos.
    assert max(f["semana"] for f in datos["filas"]) <= datos["total"]["semana"]
    assert max(f["anio"] for f in datos["filas"]) <= datos["total"]["anio"]


def client(monkeypatch, *roles):
    monkeypatch.setattr(hoja, "construir", lambda db, corte=None: datos_ejemplo())
    app = FastAPI()
    app.include_router(reportes.router, prefix="/api/reportes")
    app.dependency_overrides[get_db] = lambda: None
    user = SimpleNamespace(id=uuid4(), username="prueba", data_level_max=2, roles=[SimpleNamespace(code=c) for c in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize("role", ["DIRECTIVE", "SOURCE_UPLOADER", "ANALYST"])
def test_descarga_para_los_perfiles_del_boletin(monkeypatch, role):
    response = client(monkeypatch, role).get("/api/reportes/hoja-ejecutiva")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert "Hoja_ejecutiva_SISC_2026-09-12.pdf" in response.headers["content-disposition"]


def test_otros_perfiles_no(monkeypatch):
    assert client(monkeypatch, "PORTAL_EDITOR").get("/api/reportes/hoja-ejecutiva").status_code == 403
