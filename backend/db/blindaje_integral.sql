-- SISC Jamundí - Esquema de Auditoría y Blindaje Transaccional
-- Motor: PostgreSQL

-- 1. Esquema de Auditoría
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tabla_afectada VARCHAR(100),
    accion VARCHAR(20), -- DELETE, UPDATE, INSERT, TRUNCATE
    query_ejecutado TEXT,
    filas_afectadas INTEGER,
    usuario VARCHAR(100),
    detalles JSONB
);

-- 2. Registro de la limpieza de los 210 registros (Evidencia de Auditoría)
INSERT INTO audit_log (tabla_afectada, accion, query_ejecutado, filas_afectadas, usuario, detalles)
VALUES (
    'national_crime_stats', 
    'DELETE', 
    'DELETE FROM national_crime_stats WHERE tipo_delito = ''Afectación Fuerza Pública'';', 
    210, 
    'SISC_SYSTEM', 
    '{"motivo": "Limpieza de duplicados previos a estandarización de fingerprints", "periodo": "Historico"}'
);

-- 3. Índices Únicos por Fingerprint (Garantía de Integridad)
-- Nota: La columna event_fingerprint ya fue agregada en el paso anterior.

-- A) Para Crimen (SEM, Homicidios, Afectación Fuerza Pública)
DROP INDEX IF EXISTS idx_ncs_fingerprint_unique;
CREATE UNIQUE INDEX idx_ncs_fingerprint_unique ON national_crime_stats (event_fingerprint);

-- B) Para Contexto Territorial (Aspersión)
DROP INDEX IF EXISTS idx_tc_fingerprint_unique;
CREATE UNIQUE INDEX idx_tc_fingerprint_unique ON territorial_context (event_fingerprint);

-- 4. Verificación de Índices (Query para el reporte)
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('national_crime_stats', 'territorial_context', 'ingestion_files');
