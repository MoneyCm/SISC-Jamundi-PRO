-- Estudios del Observatorio: factores asociados, revisión posterior, pausa y trabajo de campo. Idempotente.
BEGIN;
ALTER TABLE observatory_studies ADD COLUMN IF NOT EXISTS associated_factors TEXT;
ALTER TABLE observatory_studies ADD COLUMN IF NOT EXISTS review_on DATE;
ALTER TABLE observatory_studies ADD COLUMN IF NOT EXISTS status_note TEXT;
ALTER TABLE observatory_studies ADD COLUMN IF NOT EXISTS field_notes JSONB NOT NULL DEFAULT '[]'::jsonb;
COMMIT;
