-- Harden live_account_risk_state: enable RLS + deny PostgREST roles.
-- Table may already exist from 20260722180000 without RLS.
-- Backend uses service_role / direct Postgres (bypasses RLS).
-- Version: 20260727190000

ALTER TABLE IF EXISTS public.live_account_risk_state ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.live_account_risk_state FROM anon, authenticated;
GRANT ALL ON TABLE public.live_account_risk_state TO service_role;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'live_account_risk_state'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'live_account_risk_state'
      AND policyname = 'deny_all_live_account_risk_state'
  ) THEN
    CREATE POLICY deny_all_live_account_risk_state
      ON public.live_account_risk_state
      FOR ALL
      TO anon, authenticated
      USING (false)
      WITH CHECK (false);
  END IF;
END $$;

COMMENT ON TABLE public.live_account_risk_state IS
  'Persisted peak equity HWM for live risk drawdown gates. RLS deny for anon/authenticated.';
