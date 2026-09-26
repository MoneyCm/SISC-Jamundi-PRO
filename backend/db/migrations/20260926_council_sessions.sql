-- Fechas de sesión del Consejo de Seguridad (calendario operativo). Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS council_sessions (
  id UUID PRIMARY KEY,
  instance VARCHAR(40) NOT NULL DEFAULT 'CONSEJO_SEGURIDAD',
  session_date DATE NOT NULL,
  note TEXT,
  created_by VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_council_session_date UNIQUE (instance, session_date)
);
CREATE INDEX IF NOT EXISTS ix_council_sessions_session_date ON council_sessions(session_date);
COMMIT;
