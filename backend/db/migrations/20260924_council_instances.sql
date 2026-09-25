-- Compromisos de varias instancias (Consejo, comités, reuniones) y registro de actas leídas. Idempotente.
BEGIN;
ALTER TABLE council_commitments ADD COLUMN IF NOT EXISTS instance VARCHAR(40) NOT NULL DEFAULT 'CONSEJO_SEGURIDAD';
ALTER TABLE council_commitments ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'COMPROMISO';
CREATE INDEX IF NOT EXISTS ix_council_commitments_instance ON council_commitments(instance);

CREATE TABLE IF NOT EXISTS council_act_reads (
  id UUID PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  sha256 VARCHAR(64) NOT NULL,
  instance VARCHAR(40) NOT NULL,
  act_number VARCHAR(20),
  act_date DATE,
  reading JSONB NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
  result JSONB,
  created_by VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confirmed_by VARCHAR(120),
  confirmed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_council_act_reads_sha256 ON council_act_reads(sha256);
COMMIT;
