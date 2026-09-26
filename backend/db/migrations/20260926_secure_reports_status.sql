-- Reportes seguros del portal: estado de atención e historial. Idempotente.
BEGIN;
ALTER TABLE secure_reports ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'RECIBIDO';
ALTER TABLE secure_reports ADD COLUMN IF NOT EXISTS gestion JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE secure_reports ADD COLUMN IF NOT EXISTS atendido_por VARCHAR(120);
ALTER TABLE secure_reports ADD COLUMN IF NOT EXISTS actualizado_at TIMESTAMPTZ;
ALTER TABLE secure_reports ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS ix_secure_reports_estado ON secure_reports (estado);
COMMIT;
