"""Ajustes aditivos para bases anteriores a la conciliación histórica."""

STATEMENTS = (
    "ALTER TABLE ingestion_runs ADD COLUMN IF NOT EXISTS cobertura_inicio DATE, ADD COLUMN IF NOT EXISTS cobertura_fin DATE, ADD COLUMN IF NOT EXISTS calidad_resultado VARCHAR(30), ADD COLUMN IF NOT EXISTS procesador_version VARCHAR(20) DEFAULT 'policia_processor_v1', ADD COLUMN IF NOT EXISTS homologacion_version VARCHAR(20) DEFAULT '2026.08'",
    "ALTER TABLE sabana_snapshot_rows ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64), ADD COLUMN IF NOT EXISTS identity_confidence VARCHAR(20) DEFAULT 'HIGH'",
    "ALTER TABLE sisc_cifras_publications ADD COLUMN IF NOT EXISTS methodology_version VARCHAR(10) DEFAULT '1', ADD COLUMN IF NOT EXISTS previous_version_id UUID, ADD COLUMN IF NOT EXISTS source_version_ids JSONB",
)


def ensure_conciliacion_schema(connection):
    from sqlalchemy import text

    for statement in STATEMENTS:
        connection.execute(text(statement))
