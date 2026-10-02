-- Recordatorios de solicitudes de datos que no han respondido. Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS data_request_reminders (
  id UUID PRIMARY KEY,
  request_id UUID NOT NULL REFERENCES data_requests(id) ON DELETE CASCADE,
  reminded_on DATE NOT NULL,
  channel VARCHAR(60),
  note TEXT,
  created_by VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_data_request_reminders_request_id ON data_request_reminders(request_id);
COMMIT;
