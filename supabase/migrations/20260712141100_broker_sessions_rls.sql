-- =============================================================================
-- QuantForg migration: Broker sessions RLS
-- Version: 20260712141100
-- Reversible: see supabase/migrations/down/20260712141100_broker_sessions_rls.down.sql
-- =============================================================================

ALTER TABLE public.broker_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_sessions FORCE ROW LEVEL SECURITY;

CREATE POLICY broker_sessions_select_own ON public.broker_sessions
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_sessions_insert_own ON public.broker_sessions
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_sessions_update_own ON public.broker_sessions
  FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_sessions_delete_own ON public.broker_sessions
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );
