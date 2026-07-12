-- =============================================================================
-- QuantForg migration: Broker connection health RLS
-- Version: 20260712142100
-- Reversible: see supabase/migrations/down/20260712142100_broker_health_rls.down.sql
-- Depends on: 20260712142000_broker_health, public.current_app_user_id
-- =============================================================================

ALTER TABLE public.broker_connection_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_connection_health FORCE ROW LEVEL SECURITY;

CREATE POLICY broker_connection_health_select_own
  ON public.broker_connection_health
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_connection_health_insert_own
  ON public.broker_connection_health
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_connection_health_update_own
  ON public.broker_connection_health
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

CREATE POLICY broker_connection_health_delete_own
  ON public.broker_connection_health
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );
