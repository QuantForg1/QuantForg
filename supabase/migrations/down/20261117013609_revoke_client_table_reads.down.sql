-- WARNING: re-exposes all public tables to client REST reads. Emergency rollback only.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('GRANT SELECT ON public.%I TO authenticated, anon', r.tablename);
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO authenticated, anon;
