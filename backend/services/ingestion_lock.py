"""Exclusión de trabajadores por entrega, incluso entre commits y réplicas."""
from contextlib import contextmanager
import hashlib
from sqlalchemy import text


@contextmanager
def ingestion_lock(engine, delivery_key):
    key = int.from_bytes(hashlib.sha256(str(delivery_key).encode()).digest()[:8], 'big', signed=True)
    # Una transacción separada conserva el bloqueo mientras el procesador confirma
    # lotes. Es compatible con PgBouncer en modo transaction (Neon pooler).
    with engine.connect() as connection:
        with connection.begin():
            acquired = connection.execute(
                text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': key}
            ).scalar()
            yield bool(acquired)
