"""
P2: Migration validation against real PostgreSQL.
Tests: ALTER TABLE, BYTEA, unique partial index, legacy rows, idempotent restart.
Runs against a disposable test database (sisc_migration_test).
"""
import hashlib
import json
import uuid as _uuid
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.sisc_cifras_service import SiscCifrasService

BASE_URL = "postgresql://sisc_user:sisc_password@127.0.0.1:5432"
TEST_DB = "sisc_migration_test"

ALTER_STATEMENTS = [
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS requested_filters JSONB;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS resolved_filters JSONB;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS schema_version VARCHAR(10);",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_url TEXT;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_data BYTEA;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS pdf_sha256 VARCHAR(64);",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS hash_integrity JSONB;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS suppressed_cells JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS catalog_versions_used JSONB;",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS query_hash VARCHAR(64);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sisc_cifras_query_hash ON sisc_cifras_publications (query_hash) WHERE query_hash IS NOT NULL AND status != 'SUPERSEDED';",
]


def get_conn():
    return psycopg2.connect(f"{BASE_URL}/{TEST_DB}")


def setup_database():
    conn = psycopg2.connect(f"{BASE_URL}/postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.execute(f"CREATE DATABASE {TEST_DB}")
    cur.close()
    conn.close()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sisc_cifras_publications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            status VARCHAR(20) NOT NULL DEFAULT 'PUBLISHED',
            edition_type VARCHAR(30) NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            publication_json JSONB,
            created_by VARCHAR(100),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def teardown_database():
    conn = psycopg2.connect(f"{BASE_URL}/postgres")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{TEST_DB}' AND pid != pg_backend_pid()")
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.close()
    conn.close()


@pytest.fixture(scope="module", autouse=True)
def db_setup():
    setup_database()
    yield
    teardown_database()


def run_alters():
    conn = get_conn()
    cur = conn.cursor()
    for stmt in ALTER_STATEMENTS:
        cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()


class TestAlterTables:
    def test_execute_once(self):
        run_alters()

    def test_idempotent_second_run(self):
        run_alters()

    def test_idempotent_third_run(self):
        run_alters()


class TestColumnsExist:
    def test_all_ten_columns_present(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sisc_cifras_publications'
            ORDER BY ordinal_position
        """)
        cols = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        conn.close()

        expected = {
            "requested_filters": "jsonb",
            "resolved_filters": "jsonb",
            "schema_version": "character varying",
            "pdf_url": "text",
            "pdf_data": "bytea",
            "pdf_sha256": "character varying",
            "hash_integrity": "jsonb",
            "suppressed_cells": "jsonb",
            "catalog_versions_used": "jsonb",
            "query_hash": "character varying",
        }
        for col, dtype in expected.items():
            assert col in cols, f"Column {col} missing"
            assert cols[col] == dtype, f"Column {col}: expected {dtype}, got {cols[col]}"


class TestByteaWriteRead:
    def test_pdf_roundtrip(self):
        pdf_content = b"%PDF-1.4 test binary content \x00\x01\x02\xff\xfe"
        pdf_hash = hashlib.sha256(pdf_content).hexdigest()
        pub_id = str(_uuid.uuid4())

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, pdf_data, pdf_sha256, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, %s, 'test')
        """, (pub_id, psycopg2.Binary(pdf_content), pdf_hash))
        conn.commit()

        cur.execute("SELECT pdf_data, pdf_sha256 FROM sisc_cifras_publications WHERE id = %s::uuid", (pub_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        assert row is not None, "Row not found after insert"
        actual = bytes(row[0])
        assert actual == pdf_content, f"BYTEA roundtrip failed: got {len(actual)} bytes, expected {len(pdf_content)}"
        assert row[1] == pdf_hash, "SHA256 roundtrip failed"

    def test_null_pdf_for_legacy(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, created_by)
            VALUES (gen_random_uuid(), 'WEEKLY', '2026-01-01', '2026-01-07', 'legacy')
        """)
        conn.commit()
        cur.execute("SELECT pdf_data FROM sisc_cifras_publications WHERE created_by = 'legacy'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row[0] is None, "Legacy row pdf_data should be NULL"


class TestUniquePartialIndex:
    def test_index_exists(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'sisc_cifras_publications'
            AND indexname = 'idx_sisc_cifras_query_hash'
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        assert row is not None, "Partial index idx_sisc_cifras_query_hash not found"
        assert "UNIQUE" in row[1], f"Index is not unique: {row[1]}"
        assert "WHERE" in row[1], f"Index is not partial: {row[1]}"

    def test_duplicate_hash_rejected(self):
        h1 = hashlib.sha256(b"dup-test-1").hexdigest()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, query_hash, status, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, 'PUBLISHED', 'test')
        """, (str(_uuid.uuid4()), h1))
        conn.commit()

        try:
            cur.execute("""
                INSERT INTO sisc_cifras_publications
                (id, edition_type, period_start, period_end, query_hash, status, created_by)
                VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, 'PUBLISHED', 'test')
            """, (str(_uuid.uuid4()), h1))
            conn.commit()
            pytest.fail("Duplicate query_hash on PUBLISHED rows should be rejected")
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    def test_different_hash_accepted(self):
        h2 = hashlib.sha256(b"dup-test-2").hexdigest()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, query_hash, status, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, 'PUBLISHED', 'test')
        """, (str(_uuid.uuid4()), h2))
        conn.commit()
        cur.close()
        conn.close()

    def test_superseeded_allows_same_hash(self):
        h3 = hashlib.sha256(b"super-test-1").hexdigest()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, query_hash, status, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, 'SUPERSEDED', 'test')
        """, (str(_uuid.uuid4()), h3))
        conn.commit()

        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, query_hash, status, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17', %s, 'PUBLISHED', 'test')
        """, (str(_uuid.uuid4()), h3))
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM sisc_cifras_publications WHERE query_hash = %s", (h3,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert count == 2, f"Expected 2 rows with same hash (SUPERSEDED + PUBLISHED), got {count}"


class TestLegacyRow:
    def test_new_columns_are_null(self):
        pub_json = {"period": {"start": "2026-01-01", "end": "2026-01-07"}}
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end, publication_json, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-01-01', '2026-01-07', %s, 'legacy_user')
        """, (str(_uuid.uuid4()), psycopg2.extras.Json(pub_json)))
        conn.commit()

        cur.execute("""
            SELECT requested_filters, resolved_filters, pdf_data, query_hash,
                   suppressed_cells, catalog_versions_used, hash_integrity
            FROM sisc_cifras_publications WHERE created_by = 'legacy_user'
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()

        assert row[0] is None, "Legacy: requested_filters should be NULL"
        assert row[1] is None, "Legacy: resolved_filters should be NULL"
        assert row[2] is None, "Legacy: pdf_data should be NULL"
        assert row[3] is None, "Legacy: query_hash should be NULL"
        assert row[4] is None or row[4] == [], "Legacy: suppressed_cells should be NULL or empty array"


class TestJsonbRoundtrip:
    def test_all_jsonb_columns(self):
        pub_id = str(_uuid.uuid4())
        requested = {"mode": "OFFICIAL_PUBLICATION", "preset": "semanal"}
        resolved = {"period": {"start": "2026-08-11", "end": "2026-08-17"}}
        suppressed = [{"cell_id": "c1", "reason": "MINIMUM_CELL_SIZE", "source": "POLICIA_SEMANAL", "row_label": "test", "column_label": "test"}]
        catalog_v = {"barrios": "2026.08", "conductas": "2026.08", "presets": "2026.08"}
        hash_int = {"algorithm": "sha256", "value": "a" * 64}

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sisc_cifras_publications
            (id, edition_type, period_start, period_end,
             requested_filters, resolved_filters, suppressed_cells,
             catalog_versions_used, hash_integrity, created_by)
            VALUES (%s::uuid, 'WEEKLY', '2026-08-11', '2026-08-17',
                    %s, %s, %s, %s, %s, 'jsonb_test')
        """, (
            pub_id,
            psycopg2.extras.Json(requested),
            psycopg2.extras.Json(resolved),
            psycopg2.extras.Json(suppressed),
            psycopg2.extras.Json(catalog_v),
            psycopg2.extras.Json(hash_int),
        ))
        conn.commit()

        cur.execute("""
            SELECT requested_filters, resolved_filters, suppressed_cells,
                   catalog_versions_used, hash_integrity
            FROM sisc_cifras_publications WHERE id = %s::uuid
        """, (pub_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        assert row[0]["mode"] == "OFFICIAL_PUBLICATION"
        assert row[1]["period"]["start"] == "2026-08-11"
        assert row[2][0]["reason"] == "MINIMUM_CELL_SIZE"
        assert row[3]["barrios"] == "2026.08"
        assert row[3]["conductas"] == "2026.08"
        assert row[3]["presets"] == "2026.08"
        assert row[4]["algorithm"] == "sha256"
        assert len(row[4]["value"]) == 64


class TestIdempotentRestart:
    def test_alter_again_preserves_data(self):
        run_alters()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sisc_cifras_publications")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        assert count >= 1, f"Data lost after re-running ALTERs: {count} rows"

    def test_second_alter_again_preserves_data(self):
        run_alters()


class TestDatasetIdentityIntegration:
    """Integration test: collect_dataset_identity() against real PostgreSQL."""

    @classmethod
    def setup_class(cls):
        stmts = [
            """CREATE TABLE IF NOT EXISTS hechos_seguridad (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fuente_codigo VARCHAR(50) NOT NULL,
                id_fuente VARCHAR(100),
                ingestion_id UUID,
                conducta_original VARCHAR(255),
                conducta_estandar VARCHAR(255),
                categoria_delito VARCHAR(100),
                fecha_evento DATE NOT NULL,
                hora_evento TIME,
                semana_num INTEGER,
                dia_semana VARCHAR(20),
                sexo VARCHAR(50),
                edad INTEGER,
                grupo_edad VARCHAR(50),
                zona VARCHAR(50),
                arma_medio VARCHAR(100),
                modalidad VARCHAR(100),
                barrio_original VARCHAR(150),
                barrio_normalizado VARCHAR(150),
                comuna VARCHAR(50),
                fingerprint VARCHAR(64),
                fecha_ingesta TIMESTAMPTZ DEFAULT NOW(),
                usuario_ingesta VARCHAR(100)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_hechos_source_fecha ON hechos_seguridad (fuente_codigo, fecha_evento)",
            "CREATE INDEX IF NOT EXISTS idx_hechos_fingerprint ON hechos_seguridad (fuente_codigo, fingerprint)",
            """CREATE TABLE IF NOT EXISTS inspeccion_actuaciones (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                medida_id UUID,
                fecha_actuacion TIMESTAMPTZ NOT NULL,
                fingerprint_hash VARCHAR(64),
                fuente_archivo VARCHAR(255),
                ingestion_id UUID,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_insp_fecha ON inspeccion_actuaciones (fecha_actuacion)",
            """CREATE TABLE IF NOT EXISTS institutional_data_batches (
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
            )""",
            """CREATE TABLE IF NOT EXISTS institutional_indicators (
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
            )""",
            """CREATE TABLE IF NOT EXISTS institutional_agent_runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                batch_id UUID REFERENCES institutional_data_batches(id),
                source_filename VARCHAR(255) NOT NULL,
                source_sha256 VARCHAR(64) NOT NULL,
                extractor_version VARCHAR(30) DEFAULT '1.0',
                status VARCHAR(30) DEFAULT 'RECEIVED',
                summary TEXT,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )""",
        ]
        conn = get_conn()
        cur = conn.cursor()
        for s in stmts:
            cur.execute(s)
        conn.commit()
        cur.close()
        conn.close()

    def _insert_policia(self, fingerprints):
        conn = get_conn()
        cur = conn.cursor()
        for i, fp in enumerate(fingerprints):
            cur.execute("""
                INSERT INTO hechos_seguridad
                (id, fuente_codigo, id_fuente, fecha_evento, fingerprint, conducta_estandar)
                VALUES (%s::uuid, 'POLICIA_SEMANAL', %s, '2026-08-15', %s, 'HURTO')
            """, (str(_uuid.uuid4()), f"SRC-{i}", fp))
        conn.commit()
        cur.close()
        conn.close()

    def _insert_inspeccion(self, fingerprints):
        conn = get_conn()
        cur = conn.cursor()
        for i, fp in enumerate(fingerprints):
            cur.execute("""
                INSERT INTO inspeccion_actuaciones
                (id, fecha_actuacion, fingerprint_hash, fuente_archivo)
                VALUES (%s::uuid, '2026-08-15 10:00:00+00', %s, 'carga_real.xlsx')
            """, (str(_uuid.uuid4()), fp))
        conn.commit()
        cur.close()
        conn.close()

    def _insert_comisarias(self, source_sha256, version=1):
        conn = get_conn()
        cur = conn.cursor()
        batch_id = str(_uuid.uuid4())
        cur.execute("""
            INSERT INTO institutional_data_batches
            (id, program, reporting_entity, period, cutoff_date, source_reference,
             version, validation_status, submitted_by, approved_by)
            VALUES (%s::uuid, 'COMISARIAS', 'Comisaria Jamundi', '2026-08',
                    '2026-08-15', 'ref', %s, 'APPROVED', 'test', 'admin')
        """, (batch_id, version))
        cur.execute("""
            INSERT INTO institutional_indicators
            (id, batch_id, indicator, value, is_public)
            VALUES (%s::uuid, %s::uuid, 'atenciones_total', 42, TRUE)
        """, (str(_uuid.uuid4()), batch_id))
        cur.execute("""
            INSERT INTO institutional_agent_runs
            (id, batch_id, source_filename, source_sha256, status)
            VALUES (%s::uuid, %s::uuid, 'comisarias.xlsx', %s, 'COMPLETED')
        """, (str(_uuid.uuid4()), batch_id, source_sha256))
        conn.commit()
        cur.close()
        conn.close()

    def _get_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(f"{BASE_URL}/{TEST_DB}")
        Session = sessionmaker(bind=engine)
        return Session(), engine

    def test_identity_returns_content_hashes(self):
        self._insert_policia(["fp_aaa", "fp_bbb", "fp_ccc"])
        self._insert_inspeccion(["insp_001", "insp_002"])
        self._insert_comisarias("sha_of_source_file_abc123")

        session, engine = self._get_session()
        try:
            identity = SiscCifrasService.collect_dataset_identity(
                session, date(2026, 8, 11), date(2026, 8, 17)
            )

            assert "POLICIA_SEMANAL" in identity
            assert "INSPECCIONES_RNMC" in identity
            assert "COMISARIAS_FAMILIA" in identity

            policia = identity["POLICIA_SEMANAL"]
            assert policia["unique_count"] == 3
            assert policia["content_hash"] is not None
            assert len(policia["content_hash"]) == 32

            insp = identity["INSPECCIONES_RNMC"]
            assert insp["unique_count"] == 2
            assert insp["content_hash"] is not None
            assert len(insp["content_hash"]) == 32

            comis = identity["COMISARIAS_FAMILIA"]
            assert comis["unique_count"] == 1
            assert comis["content_hash"] == "sha_of_source_file_abc123"
            assert comis["latest_batch_id"] is not None
        finally:
            session.close()
            engine.dispose()

    def test_different_data_different_hash(self):
        self._insert_policia(["fp_xxx"])

        session, engine = self._get_session()
        try:
            identity = SiscCifrasService.collect_dataset_identity(
                session, date(2026, 8, 11), date(2026, 8, 17)
            )
            hash_before = identity["POLICIA_SEMANAL"]["content_hash"]

            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO hechos_seguridad
                (id, fuente_codigo, id_fuente, fecha_evento, fingerprint, conducta_estandar)
                VALUES (%s::uuid, 'POLICIA_SEMANAL', 'NEW-1', '2026-08-14', 'fp_new', 'HURTO')
            """, (str(_uuid.uuid4()),))
            conn.commit()
            cur.close()
            conn.close()

            identity2 = SiscCifrasService.collect_dataset_identity(
                session, date(2026, 8, 11), date(2026, 8, 17)
            )
            hash_after = identity2["POLICIA_SEMANAL"]["content_hash"]
            assert hash_before != hash_after, "content_hash should change when new data added"
            assert identity2["POLICIA_SEMANAL"]["unique_count"] == 4
        finally:
            session.close()
            engine.dispose()
