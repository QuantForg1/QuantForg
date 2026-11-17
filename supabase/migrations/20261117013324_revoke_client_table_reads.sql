-- 17 Nov 2026 RLS audit, part 2: platform_risk_policy (owner-only rules) was
-- readable by every signed-in user via Supabase REST, and anon held SELECT on
-- 83 public tables. No client reads Supabase tables directly (the web app has
-- no supabase-js; the API uses the service role / direct Postgres), so all
-- direct table access for anon/authenticated is removed. RLS stays enabled.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','f') LOOP
    EXECUTE format('REVOKE ALL ON public.%I FROM authenticated, anon', r.relname);
  END LOOP;
  FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind = 'S' LOOP
    EXECUTE format('REVOKE ALL ON SEQUENCE public.%I FROM authenticated, anon', r.relname);
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM authenticated, anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM authenticated, anon;
