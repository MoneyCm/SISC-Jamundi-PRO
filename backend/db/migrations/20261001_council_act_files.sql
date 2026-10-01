-- Archivo original (PDF o Word) de cada acta leída, para el archivo de actas. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS council_act_files (
  id UUID PRIMARY KEY,
  read_id UUID NOT NULL UNIQUE REFERENCES council_act_reads(id) ON DELETE CASCADE,
  filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(120),
  size_bytes INTEGER NOT NULL,
  sha256 VARCHAR(64) NOT NULL,
  content BYTEA NOT NULL,
  uploaded_by VARCHAR(120) NOT NULL,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_council_act_files_read_id ON council_act_files(read_id);
COMMIT;
