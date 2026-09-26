BEGIN;
CREATE TABLE IF NOT EXISTS intervention_cases (
 id UUID PRIMARY KEY,
 alert_id UUID NOT NULL REFERENCES intelligence_alerts(id),
 version INTEGER NOT NULL DEFAULT 0,
 status VARCHAR(30) NOT NULL DEFAULT 'BORRADOR',
 document JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_intervention_cases_alert_id ON intervention_cases(alert_id);
CREATE TABLE IF NOT EXISTS intervention_revisions (
 id UUID PRIMARY KEY,
 case_id UUID NOT NULL REFERENCES intervention_cases(id),
 version INTEGER NOT NULL,
 action VARCHAR(30) NOT NULL,
 document JSONB NOT NULL,
 user_id VARCHAR(120) NOT NULL,
 username VARCHAR(120) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_intervention_revision UNIQUE(case_id, version)
);
CREATE INDEX IF NOT EXISTS ix_intervention_revisions_case_id ON intervention_revisions(case_id);
COMMIT;
