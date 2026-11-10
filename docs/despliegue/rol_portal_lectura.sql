-- Usuario de SOLO LECTURA para el portal ciudadano (backend con SISC_PUBLIC_ONLY=true).
-- Ejecutar una vez en la base (Neon: SQL Editor) con el usuario dueño.
-- Cambie la contraseña antes de ejecutar y guárdela solo en Render (DATABASE_URL).

CREATE ROLE sisc_portal LOGIN PASSWORD 'CAMBIAR_POR_UNA_CLAVE_LARGA';

GRANT CONNECT ON DATABASE neondb TO sisc_portal;   -- ajuste el nombre de la base si es otro
GRANT USAGE ON SCHEMA public TO sisc_portal;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sisc_portal;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sisc_portal;

-- Aunque el backend público no tiene rutas para estas tablas, el usuario tampoco puede leerlas:
-- cuentas, permisos, auditoría, denuncias recibidas, botón de pánico, casos y actas.
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

-- Sin escritura de ningún tipo.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM sisc_portal;
