-- La SEMANA 27 de 2026 (cargada el 14/07/2026 con policia_processor_v1) guardó 1.236 filas
-- con la conducta en código (HURTO_PERSONAS, LESIONES, ...). Los mismos hechos se volvieron a
-- guardar con el nombre estándar en cargas posteriores, así que aparecían dos veces en los
-- listados por delito y en los conteos de registros.
--   1. Respalda las filas en código.
--   2. Borra las que ya tienen el mismo hecho (mismo ID oficial o huella) con nombre estándar.
--   3. Pasa al nombre estándar las que no tienen gemelo.
-- Idempotente: si ya no hay filas en código, no hace nada.
BEGIN;

CREATE TABLE IF NOT EXISTS respaldo_hechos_codigo_20260927 AS
SELECT * FROM hechos_seguridad WHERE false;

INSERT INTO respaldo_hechos_codigo_20260927
SELECT h.* FROM hechos_seguridad h
WHERE h.fuente_codigo = 'POLICIA_SEMANAL' AND h.conducta_estandar ~ '^[A-Z_]+$'
  AND NOT EXISTS (SELECT 1 FROM respaldo_hechos_codigo_20260927 r WHERE r.id = h.id);

WITH llaves AS (
    SELECT id,
           conducta_estandar ~ '^[A-Z_]+$' AS en_codigo,
           CASE WHEN nullif(btrim(id_fuente), '') IS NOT NULL THEN 'ID:' || btrim(id_fuente)
                WHEN nullif(btrim(fingerprint), '') IS NOT NULL THEN 'FP:' || btrim(fingerprint)
                ELSE 'ROW:' || id END AS llave
    FROM hechos_seguridad WHERE fuente_codigo = 'POLICIA_SEMANAL'
)
DELETE FROM hechos_seguridad h
USING llaves c
WHERE h.id = c.id AND c.en_codigo
  AND EXISTS (SELECT 1 FROM llaves e WHERE e.llave = c.llave AND NOT e.en_codigo);

UPDATE hechos_seguridad SET
    conducta_estandar = CASE conducta_estandar
        WHEN 'HURTO_PERSONAS' THEN 'Hurto a personas'
        WHEN 'LESIONES' THEN 'Lesiones personales'
        WHEN 'HURTO_MOTOS' THEN 'Hurto a motocicletas'
        WHEN 'HOMICIDIO' THEN 'Homicidio'
        WHEN 'HURTO_RESIDENCIAS' THEN 'Hurto a residencias'
        WHEN 'HURTO_COMERCIO' THEN 'Hurto a comercio'
        WHEN 'HURTO_AUTOMOTORES' THEN 'Hurto a automotores'
    END,
    categoria_delito = CASE WHEN conducta_estandar = 'LESIONES' THEN 'LESIONES' ELSE categoria_delito END
WHERE fuente_codigo = 'POLICIA_SEMANAL'
  AND conducta_estandar IN ('HURTO_PERSONAS', 'LESIONES', 'HURTO_MOTOS', 'HOMICIDIO',
                            'HURTO_RESIDENCIAS', 'HURTO_COMERCIO', 'HURTO_AUTOMOTORES');

COMMIT;
