"""HTTP contract for both police upload entry points; no production DB writes.

Database and job execution are doubles. The real FastAPI route, multipart
parsing, quality gate and job arguments are exercised, not SQL persistence.
"""
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api import ingesta


CONTENT = b'HECHOS_ID,DESCRIPCION_CONDUCTA,FECHA_HECHO,NoSEMANA,BARRIOS_HECHO,MUNICIPIO_HECHO,ZONA\nTEST-1,HOMICIDIO,2026-09-01,36,CENTRO,JAMUNDI,URBANA\n'


@pytest.fixture
def rig(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.refresh.side_effect = lambda row: setattr(row, 'id', uuid4())
    quality = MagicMock(return_value={'semaforo': 'VERDE', 'score_overall': 100, 'issues': []})
    monkeypatch.setattr(ingesta.dq_service, 'run_dq', quality)
    monkeypatch.setattr(ingesta.crud_dq, 'create_dq_report', MagicMock(return_value=SimpleNamespace(id=uuid4())))
    audit = AsyncMock()
    monkeypatch.setattr(ingesta, 'log_audit', audit)
    job = MagicMock()
    monkeypatch.setattr(ingesta, '_process_policia_background', job)
    app = FastAPI()
    app.include_router(ingesta.router, prefix='/api/ingesta')
    app.dependency_overrides[ingesta.get_db] = lambda: db
    app.dependency_overrides[ingesta.ingestion_operator] = lambda: SimpleNamespace(id=uuid4(), username='contract-test')
    return SimpleNamespace(client=TestClient(app), db=db, quality=quality, job=job, audit=audit)


@pytest.mark.parametrize('dataset,extra', [('policia_semanal', {'source_name': 'POLICIA_SEMANAL_MINDEFENSA'}), ('POLICIA_SEMANAL', {})])
def test_both_forms_deliver_identical_bytes_and_processing(rig, dataset, extra):
    response = rig.client.post(f'/api/ingesta/gate/{dataset}', data=extra, files={'file': ('sabana.csv', CONTENT, 'text/csv')})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'accepted'
    assert result['ingestion_id'] == result['report_id']
    rig.quality.assert_called_once_with(CONTENT, 'sabana.csv', source_name='POLICIA_SEMANAL', profile='POLICIA_SEMANAL')
    run = rig.db.add.call_args.args[0]
    assert run.fuente_codigo == 'POLICIA_SEMANAL'
    assert run.hash_archivo == hashlib.sha256(CONTENT).hexdigest()
    assert run.status == 'IN_PROGRESS'
    assert run.resumen['dq']['semaforo'] == 'VERDE'
    rig.db.commit.assert_called_once()
    rig.job.assert_called_once_with(CONTENT, 'sabana.csv', 'contract-test', result['ingestion_id'], False)
    assert rig.audit.await_args.args[1] == 'POLICIA_SEMANAL_INGESTION_STARTED'


@pytest.mark.parametrize('dataset', ['policia_semanal', 'POLICIA_SEMANAL'])
def test_quality_rejection_never_starts_processing(rig, dataset):
    rig.quality.return_value = {'semaforo': 'ROJO', 'issues': ['invalid']}
    response = rig.client.post(f'/api/ingesta/gate/{dataset}', files={'file': ('sabana.csv', CONTENT)})
    assert response.status_code == 422
    rig.job.assert_not_called()
    rig.db.add.assert_not_called()


@pytest.mark.parametrize('dataset', ['policia_semanal', 'POLICIA_SEMANAL'])
def test_duplicate_returns_existing_delivery_without_reprocessing(rig, dataset):
    previous = SimpleNamespace(id=uuid4(), status='COMPLETED', rechazadas=0)
    rig.db.query.return_value.filter.return_value.first.side_effect = [previous, (uuid4(),)]
    response = rig.client.post(f'/api/ingesta/gate/{dataset}', files={'file': ('sabana.csv', CONTENT)})
    assert response.status_code == 200
    assert response.json()['status'] == 'skipped'
    assert response.json()['ingestion_id'] == str(previous.id)
    rig.job.assert_not_called()
    rig.db.add.assert_not_called()
