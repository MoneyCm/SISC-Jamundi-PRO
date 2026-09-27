"""Prueba con PostgreSQL real; no crea ni modifica tablas."""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from services.ingestion_lock import ingestion_lock


def test_worker_lock_survives_batch_commits_and_releases_on_failure():
    url = os.getenv('INGESTION_LOCK_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires PostgreSQL test connection')
    engine = create_engine(url)
    key = 'test:' + str(uuid.uuid4())
    try:
        with pytest.raises(RuntimeError, match='worker failed'):
            with ingestion_lock(engine, key) as acquired:
                assert acquired
                with engine.begin() as worker:
                    worker.execute(text('SELECT 1'))
                with ingestion_lock(engine, key) as second:
                    assert not second
                with ingestion_lock(engine, key + ':different') as independent:
                    assert independent
                raise RuntimeError('worker failed')
        with ingestion_lock(engine, key) as retry:
            assert retry
    finally:
        engine.dispose()
