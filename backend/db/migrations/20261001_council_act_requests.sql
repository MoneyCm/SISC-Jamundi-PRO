-- Peticiones de actas que faltan (a quién y cuándo se pidieron). Idempotente.
BEGIN;
CREATE TABLE IF NOT EXISTS council_act_requests (
  id UUID PRIMARY KEY,
  instance VARCHAR(40) NOT NULL,
  periodo VARCHAR(10) NOT NULL,
  requested_on DATE NOT NULL,
  requested_to VARCHAR(200) NOT NULL,
  note TEXT,
  times INTEGER NOT NULL DEFAULT 1,
  created_by VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by VARCHAR(120),
  updated_at TIMESTAMPTZ,
  CONSTRAINT uq_council_act_requests_periodo UNIQUE (instance, periodo)
);
COMMIT;
