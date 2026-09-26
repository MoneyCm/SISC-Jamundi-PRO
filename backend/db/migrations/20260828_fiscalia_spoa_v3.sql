CREATE TABLE IF NOT EXISTS fiscalia_spoa_runs (
    id VARCHAR(80) PRIMARY KEY,
    status VARCHAR(40) NOT NULL DEFAULT 'IN_PROGRESS',
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    source_cutoff_date DATE,
    datasets JSONB NOT NULL DEFAULT '{}'::jsonb,
    bulletin_path TEXT,
    bulletin_sha256 VARCHAR(64),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS fiscalia_spoa_snapshots (
    id UUID PRIMARY KEY,
    run_id VARCHAR(80) NOT NULL REFERENCES fiscalia_spoa_runs(id),
    dataset_key VARCHAR(20) NOT NULL,
    dataset_id VARCHAR(20) NOT NULL,
    cutoff_date DATE NOT NULL,
    metadata_sha256 VARCHAR(64) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    schema_version VARCHAR(32) NOT NULL,
    source_row_count BIGINT,
    filtered_count INTEGER DEFAULT 0,
    valid_count INTEGER DEFAULT 0,
    discarded_count INTEGER DEFAULT 0,
    discard_reasons JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spoa_snapshot_version UNIQUE (dataset_id, cutoff_date, payload_sha256)
);

CREATE TABLE IF NOT EXISTS fiscalia_spoa_records (
    id UUID PRIMARY KEY,
    snapshot_id UUID NOT NULL REFERENCES fiscalia_spoa_snapshots(id),
    dataset_key VARCHAR(20) NOT NULL,
    record_key VARCHAR(64) NOT NULL,
    entity_anonimizado TEXT NOT NULL,
    proceso_anonimizado TEXT,
    delito_id VARCHAR(50),
    delito TEXT,
    year_hecho INTEGER,
    month_hecho INTEGER,
    estado VARCHAR(80),
    etapa VARCHAR(100),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spoa_snapshot_record UNIQUE (snapshot_id, record_key)
);

CREATE INDEX IF NOT EXISTS idx_spoa_snapshot_latest ON fiscalia_spoa_snapshots(dataset_key, cutoff_date);
CREATE INDEX IF NOT EXISTS idx_spoa_record_period ON fiscalia_spoa_records(dataset_key, year_hecho, month_hecho);
CREATE INDEX IF NOT EXISTS idx_spoa_record_process ON fiscalia_spoa_records(proceso_anonimizado);

