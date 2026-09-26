-- Seguimiento semestral de las 43 acciones del PISCC 2024-2027. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS piscc_action_reports (
  id UUID PRIMARY KEY,
  action_code VARCHAR(10) NOT NULL,
  semester VARCHAR(7) NOT NULL,
  value DOUBLE PRECISION,
  status VARCHAR(20) NOT NULL DEFAULT 'EN_EJECUCION',
  reporting_entity VARCHAR(200),
  evidence TEXT,
  note TEXT,
  received_on DATE,
  created_by VARCHAR(120) NOT NULL,
  updated_by VARCHAR(120),
  version INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT uq_piscc_action_semester UNIQUE (action_code, semester)
);
CREATE INDEX IF NOT EXISTS ix_piscc_action_reports_action_code ON piscc_action_reports(action_code);
CREATE INDEX IF NOT EXISTS ix_piscc_action_reports_semester ON piscc_action_reports(semester);
COMMIT;
