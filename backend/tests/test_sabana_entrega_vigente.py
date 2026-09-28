"""El boletín puede armarse con la última sábana guardada, sin subir el archivo."""
import csv
import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import ingesta
from api.auth import get_current_user
from db.models import get_db
from db.models_hechos_seguridad import SabanaSnapshotRow
from db.session import engine
from services.entrega_vigente import entrega_vigente


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
    app.include_router(ingesta.router, prefix="/api/ingesta")
    app.dependency_overrides[get_db] = lambda: db
    user = SimpleNamespace(id=uuid4(), username="prueba", data_level_max=2, roles=[SimpleNamespace(code=c) for c in roles])
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_la_directiva_recibe_la_sabana_con_las_columnas_del_excel(db):
    entrega = entrega_vigente(db)
    if entrega is None:
        pytest.skip("Sin entregas cargadas en esta base")
    respuesta = client(db, "DIRECTIVE").get("/api/ingesta/policia/entrega-vigente/sabana")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    filas = list(csv.DictReader(io.StringIO(datos["csv"])))
    esperadas = db.query(SabanaSnapshotRow).filter(SabanaSnapshotRow.ingestion_id == entrega.run_id).count()
    assert len(filas) == esperadas and datos["run"]["id"] == str(entrega.run_id)
    assert {"HECHOS_ID", "DESCRIPCION_CONDUCTA", "NoSEMANA", "MUNICIPIO_HECHO", "MES"} <= set(filas[0])
    assert filas[0]["MES"] in {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"}
    assert datos["filename"].endswith(".csv")


def test_otros_perfiles_no(db):
    assert client(db, "PORTAL_EDITOR").get("/api/ingesta/policia/entrega-vigente/sabana").status_code == 403
