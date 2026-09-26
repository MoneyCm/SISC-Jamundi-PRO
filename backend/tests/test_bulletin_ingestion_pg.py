"""Opt-in real PostGIS regression, restricted to the disposable contract DB.

Set BULLETIN_TEST_DATABASE_URL to the temporary local PostGIS container.
Uses synthetic Excel bytes, real DQ/processor/SQL; authentication and audit
identity are isolated. Never accepts the application database name.
"""
import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from api import ingesta
from db import session as database
from db.models import Event
from db.models_hechos_seguridad import HechoSeguridad, IngestionRun, SabanaSnapshotRow


def test_both_entry_points_store_identical_history_and_map_records(monkeypatch):
    url = os.environ.get('BULLETIN_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires disposable BULLETIN_TEST_DATABASE_URL')
    parsed = make_url(url)
    assert parsed.host == '127.0.0.1' and parsed.port == 55439
    assert parsed.database == 'sisc_bulletin_contract_test'
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    with engine.begin() as connection:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE events ALTER COLUMN location_geom TYPE geometry(Point,4326) USING location_geom::geometry'))
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(ingesta, 'log_audit', AsyncMock())
    app = FastAPI()
    app.include_router(ingesta.router, prefix='/api/ingesta')
    def get_db():
        with factory() as db:
            yield db
    app.dependency_overrides[ingesta.get_db] = get_db
    app.dependency_overrides[ingesta.ingestion_operator] = lambda: SimpleNamespace(id=uuid4(), username='synthetic-test')
    rows = [
        {'HECHOS_ID': 'SYNTHETIC-1', 'DESCRIPCION_CONDUCTA': 'HOMICIDIO', 'FECHA_HECHO': '2026-08-15', 'NoSEMANA': 33, 'BARRIOS_HECHO': 'CENTRO', 'MUNICIPIO_HECHO': 'JAMUNDI', 'ZONA': 'URBANA'},
        {'HECHOS_ID': 'SYNTHETIC-2', 'DESCRIPCION_CONDUCTA': 'HURTO A PERSONAS', 'FECHA_HECHO': '2026-08-16', 'NoSEMANA': 33, 'BARRIOS_HECHO': 'CENTRO', 'MUNICIPIO_HECHO': 'JAMUNDI', 'ZONA': 'URBANA'},
    ]
    stream = io.BytesIO()
    pd.DataFrame(rows).to_excel(stream, index=False)
    contents = stream.getvalue()
    client = TestClient(app)
    results = []
    try:
        for dataset, extra in [('policia_semanal', {'source_name': 'POLICIA_SEMANAL_MINDEFENSA'}), ('POLICIA_SEMANAL', {})]:
            with engine.begin() as connection:
                connection.execute(text('TRUNCATE ingestion_runs, hechos_seguridad, events, dq_reports RESTART IDENTITY CASCADE'))
            preflight = client.post('/api/ingesta/policia/preflight', files={'file': ('synthetic.xlsx', contents)})
            assert preflight.status_code == 200, preflight.text
            assert preflight.json()['status'] != 'BLOCKED', preflight.text
            response = client.post(f'/api/ingesta/gate/{dataset}', data=extra, files={'file': ('synthetic.xlsx', contents)})
            assert response.status_code == 200, response.text
            assert response.json()['status'] == 'accepted', response.text
            with factory() as db:
                run = db.get(IngestionRun, response.json()['ingestion_id'])
                assert run.status == 'COMPLETED', run.resumen
                assert run.aprobadas == 2 and run.rechazadas == 0, run.resumen
                assert db.query(SabanaSnapshotRow).count() == 2
                assert db.query(HechoSeguridad).count() == 2
                assert db.query(Event).count() == 2
                master = db.execute(text('SELECT id_fuente, conducta_estandar, fecha_evento, fuente_codigo FROM hechos_seguridad ORDER BY id_fuente')).all()
                legacy = db.execute(text('SELECT external_id, source_name, occurrence_date, barrio, ST_AsText(location_geom) FROM events ORDER BY external_id')).all()
                results.append((master, legacy, run.resumen['snapshot'], run.aprobadas, run.rechazadas))
            duplicate = client.post(f'/api/ingesta/gate/{dataset}', files={'file': ('synthetic.xlsx', contents)})
            assert duplicate.json()['status'] == 'skipped'
            assert duplicate.json()['ingestion_id'] == response.json()['ingestion_id']
            with factory() as db:
                assert db.query(IngestionRun).count() == 1
                assert db.query(HechoSeguridad).count() == 2
                assert db.query(SabanaSnapshotRow).count() == 2
                assert db.query(Event).count() == 2
        assert results[0] == results[1]
    finally:
        engine.dispose()
