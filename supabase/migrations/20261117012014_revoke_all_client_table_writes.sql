-- 17 Nov 2026 RLS audit: the browser never writes to Supabase tables (all
-- writes go through the API using the service role / direct Postgres), yet
-- ~60 public tables let signed-in users insert/update/delete their own rows
-- via REST (e.g. audit_logs, user_risk_settings, orders, executions).
-- Clients keep SELECT under RLS; all writes are server-side only.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.%I FROM authenticated, anon', r.tablename);
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLES FROM authenticated, anon;
