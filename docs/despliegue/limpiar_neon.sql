-- Se ejecuta antes de cada copia a Neon (scripts/actualizar_portal.ps1).
-- Las tablas "respaldo_*" son copias internas de la oficina que no se suben al portal. Si quedaron
-- en Neon de una copia anterior, impiden que pg_restore --clean reemplace la extension PostGIS.
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'respaldo\_%' LOOP
    EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', t.tablename);
  END LOOP;
END $$;
