"""Asesor SISC: temas, verificación de cifras y permisos."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import asistente, ia
from api.auth import get_current_user
from db.models import get_db
from db.session import engine
from services import asistente_secretaria as asesor


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    session.commit = session.flush
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_cambio_y_normalizacion():
    assert asesor.cambio(18, 12) == "subió en 6" and asesor.cambio(1, 2) == "bajó en 1" and asesor.cambio(3, 3) == "igual"
    assert asesor.normalizar("¿Cómo va la Policía?") == "¿como va la policia?"


def test_detecta_delito_y_entidad(db):
    temas = asesor.detectar_temas(db, "¿Qué compromisos tiene la Policía sobre los homicidios?")
    assert "Homicidio" in temas["delitos"] and "Policía" in temas["entidades"]


def _preparar(monkeypatch, gemini, mistral=None):
    monkeypatch.setattr(ia, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(ia, "MISTRAL_API_KEY", "x" if mistral else None)

    async def llamar_gemini(prompt):
        return gemini(prompt)

    async def llamar_mistral(prompt):
        return mistral(prompt)

    monkeypatch.setattr(ia, "call_gemini", llamar_gemini)
    monkeypatch.setattr(ia, "call_mistral", llamar_mistral)


def test_texto_con_cifras_del_expediente_se_acepta(db, monkeypatch):
    try:
        expediente, extra = asesor.construir_expediente(db, "¿Cómo vamos?")
    except ValueError:
        pytest.skip("Sin sábana cargada")
    total = extra["datos"]["total"]
    _preparar(monkeypatch, lambda p: f"Esta semana hubo {total['semana']} delitos y la anterior {total['semana_anterior']}.")
    r = asyncio.run(asesor.responder(db, "¿Cómo vamos?"))
    assert r["redactada_por"] == "Gemini" and str(total["semana"]) in r["respuesta"]


def test_cifra_inventada_se_rechaza_y_responde_sin_ia(db, monkeypatch):
    try:
        asesor.construir_expediente(db, "¿Cómo vamos?")
    except ValueError:
        pytest.skip("Sin sábana cargada")
    _preparar(monkeypatch, lambda p: "Esta semana hubo 98765 delitos.", mistral=lambda p: "Hubo 43210 homicidios.")
    r = asyncio.run(asesor.responder(db, "¿Cómo vamos?"))
    assert r["redactada_por"] == "SISC (sin IA)"
    assert "98765" not in r["respuesta"] and "43210" not in r["respuesta"] and r["respuesta"].startswith("•")


def client(db, monkeypatch, *roles):
    async def falso(db, pregunta, historial=None, hoy=None):
        return {"respuesta": "ok", "verificada": True, "redactada_por": "Gemini", "fuentes": [], "sugerencias": [], "temas": {}}
    monkeypatch.setattr(asesor, "responder", falso)
    app = FastAPI()
    app.include_router(asistente.router, prefix="/api/asistente")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba", data_level_max=2, roles=[SimpleNamespace(code=c) for c in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_permisos(db, monkeypatch):
    assert client(db, monkeypatch, "DIRECTIVE").post("/api/asistente/preguntar", json={"pregunta": "¿Cómo vamos?"}).status_code == 200
    assert client(db, monkeypatch, "SOURCE_UPLOADER").post("/api/asistente/preguntar", json={"pregunta": "¿Cómo vamos?"}).status_code == 403


def test_pregunta_de_convivencia_trae_comparendos(db):
    """Con o sin comparendos cargados, la pregunta de convivencia agrega su bloque al expediente."""
    expediente, _extra = asesor.construir_expediente(db, "¿Cómo va la convivencia este año?")
    titulos = [titulo for titulo, _ in expediente.bloques]
    assert any(titulo.startswith("Convivencia") for titulo in titulos)
    # Una pregunta solo de delitos no lo trae.
    expediente, _extra = asesor.construir_expediente(db, "¿Cómo van los homicidios?")
    assert not any(titulo.startswith("Convivencia") for titulo, _ in expediente.bloques)

