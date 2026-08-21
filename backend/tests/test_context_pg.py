"""
PostgreSQL integration: _latest_approved_context_batch() against real DB.
Verifies the full SQL query + Python post-filters execute correctly on PostgreSQL.
Disposable database sisc_context_pg_test — no production data touched.
"""
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.sisc_cifras_service import SiscCifrasService

BASE_URL = "postgresql://sisc_user:sisc_password@127.0.0.1:5432"
TEST_DB = "sisc_context_pg_test"


def _conn(db=TEST_DB):
    return psycopg2.connect(f"{BASE_URL}/{db}")


def _setup_db():
    admin = psycopg2.connect(f"{BASE_URL}/postgres")
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.execute(f"CREATE DATABASE {TEST_DB}")
    cur.close()
    admin.close()

    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE institutional_data_batches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program VARCHAR(80) NOT NULL,
            reporting_entity VARCHAR(180) NOT NULL,
            period VARCHAR(7) NOT NULL,
            cutoff_date DATE NOT NULL,
            reporting_basis VARCHAR(20) DEFAULT 'CUMULATIVE',
            source_reference VARCHAR(500) NOT NULL,
            source_filename VARCHAR(255),
            version INTEGER NOT NULL DEFAULT 1,
            validation_status VARCHAR(20) DEFAULT 'PENDING',
            submitted_by VARCHAR(100) NOT NULL,
            approved_by VARCHAR(100),
            review_notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            approved_at TIMESTAMPTZ
        )
    """)
    cur.execute("""
        CREATE TABLE institutional_indicators (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id UUID NOT NULL REFERENCES institutional_data_batches(id),
            indicator VARCHAR(220) NOT NULL,
            category VARCHAR(160),
            value NUMERIC(16,2) NOT NULL,
            unit VARCHAR(40) DEFAULT 'casos',
            is_public BOOLEAN DEFAULT TRUE,
            privacy_threshold INTEGER DEFAULT 10,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _teardown_db():
    admin = psycopg2.connect(f"{BASE_URL}/postgres")
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(
        "SELECT pg_terminate_backend(pid) "
        "FROM pg_stat_activity "
        f"WHERE datname = '{TEST_DB}' AND pid != pg_backend_pid()"
    )
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.close()
    admin.close()


@pytest.fixture(scope="module", autouse=True)
def pg_db():
    _setup_db()
    yield
    _teardown_db()


def _insert_batch(program, entity, period, cutoff, *,
                  version=1, status="APPROVED", created_at=None,
                  basis="CUMULATIVE"):
    batch_id = str(__import__("uuid").uuid4())
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO institutional_data_batches
            (id, program, reporting_entity, period, cutoff_date,
             reporting_basis, source_reference,
             version, validation_status, submitted_by, approved_by, created_at)
        VALUES (%s::uuid, %s, %s, %s, %s, %s, 'ref', %s, %s, 'test', 'admin', %s)
    """, (batch_id, program, entity, period, cutoff, basis,
          version, status, created_at))
    conn.commit()
    cur.close()
    conn.close()
    return batch_id


def _insert_indicator(batch_id, name, value, *, is_public=True, threshold=10):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO institutional_indicators
            (id, batch_id, indicator, value, is_public, privacy_threshold)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
    """, (str(__import__("uuid").uuid4()), batch_id, name, value,
          is_public, threshold))
    conn.commit()
    cur.close()
    conn.close()


def _get_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"{BASE_URL}/{TEST_DB}")
    Session = sessionmaker(bind=engine)
    return Session(), engine


def _query(period_end):
    session, engine = _get_session()
    try:
        return SiscCifrasService._latest_approved_context_batch(
            session, "COMISARIAS", period_end,
        )
    finally:
        session.close()
        engine.dispose()


class TestContextBatchPG:
    """Each test inserts its own rows and queries against real PostgreSQL."""

    def test_program_filter(self):
        """Only batches with program='COMISARIAS' are returned."""
        _insert_batch("POLICIA", "E_X", "2026-06", "2026-06-30",
                      created_at="2026-07-01 10:00:00+00")
        _insert_batch("COMISARIAS", "E_X", "2026-06", "2026-06-30",
                      created_at="2026-07-01 10:00:00+00")

        result = _query(date(2026, 7, 27))
        programs = {b.program for b in result if b.reporting_entity == "E_X"}
        assert programs == {"COMISARIAS"}, f"Only COMISARIAS should appear, got {programs}"

    def test_validation_status_filter(self):
        """Only APPROVED batches are returned."""
        _insert_batch("COMISARIAS", "E_STAT", "2026-06", "2026-06-30",
                      status="PENDING", created_at="2026-07-01 10:00:00+00")
        _insert_batch("COMISARIAS", "E_STAT", "2026-06", "2026-06-30",
                      status="APPROVED", version=2,
                      created_at="2026-07-01 10:00:00+00")

        result = _query(date(2026, 7, 27))
        e_stat = [b for b in result if b.reporting_entity == "E_STAT"]
        assert len(e_stat) == 1, f"Only 1 APPROVED batch expected, got {len(e_stat)}"
        assert e_stat[0].validation_status == "APPROVED"

    def test_cutoff_date_excludes_future_month(self):
        """Batch with cutoff_date=Jul 31 excluded when period_end=Jul 27."""
        _insert_batch("COMISARIAS", "E_CUT", "2026-07", "2026-07-31",
                      created_at="2026-07-15 10:00:00+00")
        _insert_batch("COMISARIAS", "E_CUT", "2026-06", "2026-06-30",
                      created_at="2026-07-01 10:00:00+00",
                      version=2)

        result = _query(date(2026, 7, 27))
        e_cut = [b for b in result if b.reporting_entity == "E_CUT"]
        assert len(e_cut) == 1, f"Only Jun batch should survive cutoff filter, got {len(e_cut)}"
        assert e_cut[0].period == "2026-06", f"Expected Jun, got {e_cut[0].period}"

    def test_created_at_before_next_day(self):
        """Batch created at Jul 28 12:00 excluded when period_end=Jul 27.
        next_day = Jul 28 00:00; created_at(12:00) is NOT < next_day."""
        _insert_batch("COMISARIAS", "E_LATE", "2026-06", "2026-06-30",
                      created_at="2026-07-28 12:00:00+00")

        result = _query(date(2026, 7, 27))
        e_late = [b for b in result if b.reporting_entity == "E_LATE"]
        assert len(e_late) == 0, (
            f"Batch created Jul 28 12:00 should be excluded for period_end=Jul 27, "
            f"got {len(e_late)}"
        )

    def test_created_at_exact_midnight_boundary(self):
        """Batch created at Jul 28 00:00:00 is NOT < next_day(00:00), excluded."""
        _insert_batch("COMISARIAS", "E_MID", "2026-06", "2026-06-30",
                      created_at="2026-07-28 00:00:00+00")

        result = _query(date(2026, 7, 27))
        e_mid = [b for b in result if b.reporting_entity == "E_MID"]
        assert len(e_mid) == 0, (
            "Batch created at exactly midnight Jul 28 should be excluded "
            "(created_at < next_day is strict less-than)"
        )

    def test_created_at_23h59_included(self):
        """Batch created Jul 27 23:59 is < next_day(Jul 28 00:00), included."""
        batch_id = _insert_batch("COMISARIAS", "E_23", "2026-06", "2026-06-30",
                                 created_at="2026-07-27 23:59:59+00")
        _insert_indicator(batch_id, "VIIF", 20)

        result = _query(date(2026, 7, 27))
        e_23 = [b for b in result if b.reporting_entity == "E_23"]
        assert len(e_23) == 1, (
            "Batch created Jul 27 23:59 should be included"
        )

    def test_only_closed_months(self):
        """Non-closed month (cutoff < last calendar day) excluded by _is_month_closed."""
        _insert_batch("COMISARIAS", "E_OPEN", "2026-06", "2026-06-25",
                      created_at="2026-06-26 10:00:00+00")
        _insert_batch("COMISARIAS", "E_OPEN", "2026-06", "2026-06-30",
                      created_at="2026-06-26 10:00:00+00",
                      version=2)

        result = _query(date(2026, 7, 27))
        e_open = [b for b in result if b.reporting_entity == "E_OPEN"]
        assert len(e_open) == 1, f"Only closed batch should survive, got {len(e_open)}"
        assert e_open[0].cutoff_date == date(2026, 6, 30)

    def test_duplicate_entity_selects_highest_version(self):
        """Two versions of same entity → latest_batches_by_entity picks highest version."""
        v1_id = _insert_batch("COMISARIAS", "E_DUP", "2026-06", "2026-06-30",
                              version=1, created_at="2026-06-28 10:00:00+00")
        _insert_indicator(v1_id, "VIIF", 10)
        v2_id = _insert_batch("COMISARIAS", "E_DUP", "2026-06", "2026-06-30",
                              version=2, created_at="2026-06-30 10:00:00+00")
        _insert_indicator(v2_id, "VIIF", 25)

        result = _query(date(2026, 7, 27))
        e_dup = [b for b in result if b.reporting_entity == "E_DUP"]
        assert len(e_dup) == 1, f"Entity dedup should produce 1 batch, got {len(e_dup)}"
        assert e_dup[0].version == 2, f"Version 2 should win, got v{e_dup[0].version}"

    def test_multi_entity_returns_one_per_entity(self):
        """Different entities each get their own batch in the result."""
        _insert_batch("COMISARIAS", "E_ALPHA", "2026-06", "2026-06-30",
                      created_at="2026-07-01 10:00:00+00")
        _insert_batch("COMISARIAS", "E_BETA", "2026-05", "2026-05-31",
                      created_at="2026-06-01 10:00:00+00")

        result = _query(date(2026, 7, 27))
        entities = {b.reporting_entity for b in result}
        assert "E_ALPHA" in entities, "E_ALPHA should be present"
        assert "E_BETA" in entities, "E_BETA should be present"
