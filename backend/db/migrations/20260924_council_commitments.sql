-- Compromisos de los Consejos de Seguridad y su historial de seguimiento. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS council_commitments (
  id UUID PRIMARY KEY,
  code VARCHAR(40) NOT NULL UNIQUE,
  origin_date DATE,
  origin_act VARCHAR(120),
  session_type VARCHAR(60),
  text TEXT NOT NULL,
  responsible VARCHAR(300),
  deadline_text VARCHAR(200),
  deadline_date DATE,
  status VARCHAR(30) NOT NULL DEFAULT 'SIN_INFORMACION',
  validated VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE',
  priority VARCHAR(30),
  theme VARCHAR(120),
  territory VARCHAR(200),
  mentions INTEGER NOT NULL DEFAULT 1,
  last_mention_date DATE,
  source_ref TEXT,
  notes TEXT,
  extra JSONB NOT NULL DEFAULT '{}'::jsonb,
  version INTEGER NOT NULL DEFAULT 0,
  updated_by VARCHAR(120),
  updated_at TIMESTAMPTZ DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_council_commitments_status ON council_commitments(status);
CREATE INDEX IF NOT EXISTS ix_council_commitments_theme ON council_commitments(theme);
CREATE INDEX IF NOT EXISTS ix_council_commitments_origin_date ON council_commitments(origin_date);
CREATE INDEX IF NOT EXISTS ix_council_commitments_deadline_date ON council_commitments(deadline_date);

CREATE TABLE IF NOT EXISTS council_commitment_updates (
  id UUID PRIMARY KEY,
  commitment_id UUID NOT NULL REFERENCES council_commitments(id),
  version INTEGER NOT NULL,
  action VARCHAR(30) NOT NULL,
  previous_status VARCHAR(30),
  new_status VARCHAR(30),
  note TEXT,
  evidence_url TEXT,
  username VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_council_commitment_updates_commitment ON council_commitment_updates(commitment_id);
COMMIT;
