-- SISC Jamundí - Cierre Total Anti-Duplicados
-- Motor: PostgreSQL

BEGIN;

-- 1. Estandarización de ingestion_files
-- Eliminamos el unique anterior y creamos el compuesto
ALTER TABLE ingestion_files DROP CONSTRAINT IF EXISTS ingestion_files_file_hash_key;
DROP INDEX IF EXISTS ingestion_files_file_hash_key;
ALTER TABLE ingestion_files DROP CONSTRAINT IF EXISTS uq_source_file_hash;
ALTER TABLE ingestion_files ADD CONSTRAINT uq_source_file_hash UNIQUE (source_type, file_hash);

-- 2. Preparación de tablas finales (source_id y event_fingerprint)

-- A) National Crime Stats
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='national_crime_stats' AND COLUMN_NAME='source_id') THEN
        ALTER TABLE national_crime_stats ADD COLUMN source_id VARCHAR(50);
    END IF;
END $$;

-- Poblar source_id a partir de tipo_delito para registros existentes
UPDATE national_crime_stats SET source_id = 'AFECTACION_FUERZA_PUBLICA' WHERE tipo_delito = 'Afectación Fuerza Pública' AND source_id IS NULL;
UPDATE national_crime_stats SET source_id = 'SEM_POLICIA' WHERE tipo_delito != 'Afectación Fuerza Pública' AND source_id IS NULL;

-- B) Territorial Context
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='territorial_context' AND COLUMN_NAME='source_id') THEN
        ALTER TABLE territorial_context ADD COLUMN source_id VARCHAR(50);
    END IF;
END $$;

UPDATE territorial_context SET source_id = 'ASPERSION' WHERE fuente_id = 'ASPERSION' AND source_id IS NULL;

-- 3. Índices Únicos por (source_id, event_fingerprint)
-- Limpiar nulos antes de aplicar unique
DELETE FROM national_crime_stats WHERE event_fingerprint IS NULL;
DELETE FROM territorial_context WHERE event_fingerprint IS NULL;

-- National Crime Stats
DROP INDEX IF EXISTS idx_ncs_fingerprint_unique;
DROP INDEX IF EXISTS idx_ncs_source_fingerprint_unique;
CREATE UNIQUE INDEX idx_ncs_source_fingerprint_unique ON national_crime_stats (source_id, event_fingerprint);

-- Territorial Context
DROP INDEX IF EXISTS idx_tc_fingerprint_unique;
DROP INDEX IF EXISTS idx_tc_source_fingerprint_unique;
CREATE UNIQUE INDEX idx_tc_source_fingerprint_unique ON territorial_context (source_id, event_fingerprint);

-- 4. Auditoría de Cierre
INSERT INTO audit_log (tabla_afectada, accion, query_ejecutado, filas_afectadas, usuario, detalles)
VALUES (
    'ALL_FINAL_TABLES', 
    'UPGRADE_SECURITY', 
    'UNIQUE(source_id, event_fingerprint)', 
    0, 
    'SISC_SYSTEM', 
    '{"pasos": ["Composite Unique Ingestion", "Composite Unique Stats", "Source_ID addition"]}'
);

COMMIT;
