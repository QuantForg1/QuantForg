-- 17 Nov 2026 RLS audit: signed-in users could write these tables directly
-- through Supabase REST (anon key + JWT), e.g. grant themselves a license or
-- register another user's MT5 login. The backend writes them with the
-- service role / direct Postgres, which bypass these grants.
REVOKE INSERT, UPDATE, DELETE ON public.licenses FROM authenticated, anon;
REVOKE INSERT, UPDATE, DELETE ON public.broker_accounts FROM authenticated, anon;
REVOKE INSERT, UPDATE, DELETE ON public.mt5_connections FROM authenticated, anon;
REVOKE INSERT, UPDATE, DELETE ON public.users FROM authenticated, anon;
REVOKE INSERT, UPDATE, DELETE ON public.billing_orders FROM authenticated, anon;
REVOKE INSERT, UPDATE, DELETE ON public.billing_trials FROM authenticated, anon;
REVOKE ALL ON public.licenses, public.broker_accounts, public.mt5_connections,
  public.users, public.billing_orders, public.billing_trials,
  public.notifications FROM anon;
