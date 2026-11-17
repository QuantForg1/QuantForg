-- WARNING: restores the insecure pre-audit grants (Supabase defaults). Emergency rollback only.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('GRANT INSERT, UPDATE, DELETE, TRUNCATE ON public.%I TO authenticated, anon', r.tablename);
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO authenticated, anon;
