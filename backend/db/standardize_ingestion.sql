-- SISC Jamundí - Estandarización de Ingesta y Huella Digital
-- Motor: PostgreSQL

-- 1. Registro de Archivos (Ingestión Controlada)
CREATE TABLE IF NOT EXISTS ingestion_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- SEM_POLICIA, AFECTACION, ASPERSION, etc.
    file_hash VARCHAR(64) UNIQUE,     -- Para evitar cargar el mismo archivo físico dos veces
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    records_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'SUCCESS'
);

-- 2. Agregar Huella Digital (Fingerprint) a NationalCrimeStats
-- Si la tabla ya existe, nos aseguramos de tener la columna para el UPSERT
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='national_crime_stats' AND COLUMN_NAME='event_fingerprint') THEN
        ALTER TABLE national_crime_stats ADD COLUMN event_fingerprint VARCHAR(64);
    END IF;
END $$;

-- 3. Crear Índice Único Estricto para UPSERT
-- Combinación de factores únicos: Fecha + Municipio + Delito + Modalidad + Institución + Cantidad
DROP INDEX IF EXISTS idx_ncs_fingerprint_unique;
CREATE UNIQUE INDEX idx_ncs_fingerprint_unique ON national_crime_stats (event_fingerprint);

-- 4. Aplicar misma lógica a Contexto Territorial
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='territorial_context' AND COLUMN_NAME='event_fingerprint') THEN
        ALTER TABLE territorial_context ADD COLUMN event_fingerprint VARCHAR(64);
    END IF;
END $$;

DROP INDEX IF EXISTS idx_tc_fingerprint_unique;
CREATE UNIQUE INDEX idx_tc_fingerprint_unique ON territorial_context (event_fingerprint);
