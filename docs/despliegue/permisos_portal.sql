-- Permisos del usuario de solo lectura sisc_portal. Se puede ejecutar las veces que sea necesario.
-- scripts/actualizar_portal.ps1 lo aplica después de cada copia, porque la copia vuelve a crear las tablas.

GRANT CONNECT ON DATABASE neondb TO sisc_portal;
GRANT USAGE ON SCHEMA public TO sisc_portal;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sisc_portal;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sisc_portal;

REVOKE SELECT ON
    users, user_roles, roles, permissions, access_requests, audit_log,
    report_download_tokens, report_download_audit, report_recipients, report_notification_log,
    secure_reports, panic_alerts, panic_evidences,
    vif_cases, vif_deliveries, vif_settings,
    intervention_cases, intervention_revisions,
    council_act_files, council_act_reads, council_act_requests,
    data_requests, data_request_entities, data_request_reminders,
    inspeccion_funcionarios, inspeccion_finanzas
FROM sisc_portal;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM sisc_portal;
