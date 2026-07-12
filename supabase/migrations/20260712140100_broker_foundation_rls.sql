-- =============================================================================
-- QuantForg migration: Broker Foundation RLS
-- Version: 20260712140100
-- Reversible: see supabase/migrations/down/20260712140100_broker_foundation_rls.down.sql
-- Depends on: 20260712140000_broker_foundation, public.current_app_user_id
-- =============================================================================

ALTER TABLE public.broker_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_connections ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.broker_capabilities FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_credentials FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_connections FORCE ROW LEVEL SECURITY;

-- Capabilities: authenticated may read; writes via service_role / admin API
CREATE POLICY broker_capabilities_select_authenticated
  ON public.broker_capabilities FOR SELECT TO authenticated
  USING (true);

-- Accounts: owner-only
CREATE POLICY broker_accounts_select_own ON public.broker_accounts
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY broker_accounts_insert_own ON public.broker_accounts
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY broker_accounts_update_own ON public.broker_accounts
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY broker_accounts_delete_own ON public.broker_accounts
  FOR DELETE TO authenticated
  USING (user_id = public.current_app_user_id());

-- Credentials: owner via account ownership (never expose payload in views)
CREATE POLICY broker_credentials_select_own ON public.broker_credentials
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_credentials_insert_own ON public.broker_credentials
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_credentials_update_own ON public.broker_credentials
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

CREATE POLICY broker_credentials_delete_own ON public.broker_credentials
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

-- Connections: owner via account ownership
CREATE POLICY broker_connections_select_own ON public.broker_connections
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_connections_insert_own ON public.broker_connections
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY broker_connections_update_own ON public.broker_connections
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

CREATE POLICY broker_connections_delete_own ON public.broker_connections
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.broker_accounts a
      WHERE a.id = broker_account_id
        AND a.user_id = public.current_app_user_id()
    )
  );
