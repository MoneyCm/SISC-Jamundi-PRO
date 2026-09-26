-- Solicitudes de datos a Inspecciones, Comisarías y otras dependencias. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS data_request_entities (
  id UUID PRIMARY KEY,
  name VARCHAR(200) NOT NULL UNIQUE,
  program VARCHAR(20) NOT NULL DEFAULT 'OTRA',
  cadence VARCHAR(20) NOT NULL DEFAULT 'SEMANAL',
  contact VARCHAR(300),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_requests (
  id UUID PRIMARY KEY,
  entity_id UUID NOT NULL REFERENCES data_request_entities(id) ON DELETE CASCADE,
  what VARCHAR(300) NOT NULL,
  period_start DATE,
  period_end DATE,
  requested_on DATE NOT NULL,
  due_on DATE NOT NULL,
  channel VARCHAR(60),
  status VARCHAR(20) NOT NULL DEFAULT 'PEDIDA',
  received_on DATE,
  note TEXT,
  created_by VARCHAR(120) NOT NULL,
  updated_by VARCHAR(120),
  version INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_data_requests_entity_id ON data_requests(entity_id);
CREATE INDEX IF NOT EXISTS ix_data_requests_requested_on ON data_requests(requested_on);
CREATE INDEX IF NOT EXISTS ix_data_requests_status ON data_requests(status);
COMMIT;
