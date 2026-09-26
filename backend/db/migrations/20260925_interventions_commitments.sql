-- Una intervención puede nacer de una alerta o de un compromiso del Consejo. Idempotente.
BEGIN;
ALTER TABLE intervention_cases ALTER COLUMN alert_id DROP NOT NULL;
ALTER TABLE intervention_cases ADD COLUMN IF NOT EXISTS commitment_code VARCHAR(40);
CREATE INDEX IF NOT EXISTS ix_intervention_cases_commitment_code ON intervention_cases(commitment_code);
DO $$ BEGIN
  ALTER TABLE intervention_cases ADD CONSTRAINT ck_intervention_origin
    CHECK (alert_id IS NOT NULL OR commitment_code IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
COMMIT;
