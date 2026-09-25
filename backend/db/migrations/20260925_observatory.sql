-- Estudios y recomendaciones del Observatorio del Delito. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS observatory_studies (
  id UUID PRIMARY KEY,
  code VARCHAR(20) NOT NULL UNIQUE,
  title VARCHAR(200) NOT NULL,
  question TEXT NOT NULL,
  phenomenon VARCHAR(120),
  territory VARCHAR(200),
  period_start DATE,
  period_end DATE,
  sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  hypotheses TEXT,
  findings TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
  access_level VARCHAR(20) NOT NULL DEFAULT 'INSTITUCIONAL',
  created_by VARCHAR(120) NOT NULL,
  updated_by VARCHAR(120),
  version INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_observatory_studies_status ON observatory_studies(status);

CREATE TABLE IF NOT EXISTS observatory_recommendations (
  id UUID PRIMARY KEY,
  code VARCHAR(20) NOT NULL UNIQUE,
  study_id UUID REFERENCES observatory_studies(id) ON DELETE SET NULL,
  title VARCHAR(200) NOT NULL,
  text TEXT NOT NULL,
  addressed_to VARCHAR(200),
  priority VARCHAR(10) NOT NULL DEFAULT 'MEDIA',
  status VARCHAR(20) NOT NULL DEFAULT 'PROPUESTA',
  presented_on DATE,
  decided_on DATE,
  decision_note TEXT,
  commitment_code VARCHAR(40),
  due_date DATE,
  history JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_by VARCHAR(120) NOT NULL,
  updated_by VARCHAR(120),
  version INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_observatory_recommendations_study ON observatory_recommendations(study_id);
CREATE INDEX IF NOT EXISTS ix_observatory_recommendations_status ON observatory_recommendations(status);
CREATE INDEX IF NOT EXISTS ix_observatory_recommendations_commitment ON observatory_recommendations(commitment_code);
COMMIT;
