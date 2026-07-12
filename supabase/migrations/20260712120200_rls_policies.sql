-- =============================================================================
-- QuantForg migration: Row Level Security policies
-- Version: 20260712120200
-- Reversible: see supabase/migrations/down/20260712120200_rls_policies.down.sql
-- =============================================================================

-- Map Supabase Auth uid() → application users.id (requires public.users).
CREATE OR REPLACE FUNCTION public.current_app_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT u.id
  FROM public.users AS u
  WHERE u.auth_user_id = auth.uid()
  LIMIT 1;
$$;

COMMENT ON FUNCTION public.current_app_user_id() IS
  'Resolves auth.uid() to public.users.id for Row Level Security policies.';

REVOKE ALL ON FUNCTION public.current_app_user_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_app_user_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.current_app_user_id() TO service_role;

-- ---------------------------------------------------------------------------
-- Enable RLS on every user-facing / domain table
-- ---------------------------------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brokers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Force RLS for table owners as well (defense in depth).
ALTER TABLE public.users FORCE ROW LEVEL SECURITY;
ALTER TABLE public.brokers FORCE ROW LEVEL SECURITY;
ALTER TABLE public.licenses FORCE ROW LEVEL SECURITY;
ALTER TABLE public.symbols FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trading_accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trading_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_metadata FORCE ROW LEVEL SECURITY;
ALTER TABLE public.risk_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE public.orders FORCE ROW LEVEL SECURITY;
ALTER TABLE public.positions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trades FORCE ROW LEVEL SECURITY;
ALTER TABLE public.signals FORCE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs FORCE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- users: self read/update; no self-delete
-- ---------------------------------------------------------------------------
CREATE POLICY users_select_own
  ON public.users FOR SELECT TO authenticated
  USING (id = public.current_app_user_id() OR auth_user_id = auth.uid());

CREATE POLICY users_update_own
  ON public.users FOR UPDATE TO authenticated
  USING (id = public.current_app_user_id() OR auth_user_id = auth.uid())
  WITH CHECK (id = public.current_app_user_id() OR auth_user_id = auth.uid());

CREATE POLICY users_insert_own
  ON public.users FOR INSERT TO authenticated
  WITH CHECK (auth_user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- brokers / symbols: catalogue read for authenticated; writes via service_role
-- ---------------------------------------------------------------------------
CREATE POLICY brokers_select_authenticated
  ON public.brokers FOR SELECT TO authenticated
  USING (true);

CREATE POLICY symbols_select_authenticated
  ON public.symbols FOR SELECT TO authenticated
  USING (true);

-- ---------------------------------------------------------------------------
-- licenses: owner only
-- ---------------------------------------------------------------------------
CREATE POLICY licenses_select_own
  ON public.licenses FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY licenses_insert_own
  ON public.licenses FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY licenses_update_own
  ON public.licenses FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- ---------------------------------------------------------------------------
-- trading_accounts: owner only
-- ---------------------------------------------------------------------------
CREATE POLICY trading_accounts_select_own
  ON public.trading_accounts FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY trading_accounts_insert_own
  ON public.trading_accounts FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY trading_accounts_update_own
  ON public.trading_accounts FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- ---------------------------------------------------------------------------
-- trading_sessions: owner only
-- ---------------------------------------------------------------------------
CREATE POLICY trading_sessions_select_own
  ON public.trading_sessions FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY trading_sessions_insert_own
  ON public.trading_sessions FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY trading_sessions_update_own
  ON public.trading_sessions FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- ---------------------------------------------------------------------------
-- strategy_metadata: owner CRUD
-- ---------------------------------------------------------------------------
CREATE POLICY strategy_metadata_select_own
  ON public.strategy_metadata FOR SELECT TO authenticated
  USING (owner_user_id = public.current_app_user_id());

CREATE POLICY strategy_metadata_insert_own
  ON public.strategy_metadata FOR INSERT TO authenticated
  WITH CHECK (owner_user_id = public.current_app_user_id());

CREATE POLICY strategy_metadata_update_own
  ON public.strategy_metadata FOR UPDATE TO authenticated
  USING (owner_user_id = public.current_app_user_id())
  WITH CHECK (owner_user_id = public.current_app_user_id());

CREATE POLICY strategy_metadata_delete_own
  ON public.strategy_metadata FOR DELETE TO authenticated
  USING (owner_user_id = public.current_app_user_id());

-- ---------------------------------------------------------------------------
-- risk_profiles: owner CRUD
-- ---------------------------------------------------------------------------
CREATE POLICY risk_profiles_select_own
  ON public.risk_profiles FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY risk_profiles_insert_own
  ON public.risk_profiles FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY risk_profiles_update_own
  ON public.risk_profiles FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY risk_profiles_delete_own
  ON public.risk_profiles FOR DELETE TO authenticated
  USING (user_id = public.current_app_user_id());

-- ---------------------------------------------------------------------------
-- orders / positions / trades: via owned trading account
-- ---------------------------------------------------------------------------
CREATE POLICY orders_select_own
  ON public.orders FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = orders.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY orders_insert_own
  ON public.orders FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY orders_update_own
  ON public.orders FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = orders.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY positions_select_own
  ON public.positions FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = positions.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY positions_insert_own
  ON public.positions FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY positions_update_own
  ON public.positions FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = positions.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

-- trades: select + insert only (append-only enforced by triggers)
CREATE POLICY trades_select_own
  ON public.trades FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trades.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY trades_insert_own
  ON public.trades FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

-- ---------------------------------------------------------------------------
-- signals: own account signals, or unscoped catalogue signals the user owns via strategy
-- ---------------------------------------------------------------------------
CREATE POLICY signals_select_own
  ON public.signals FOR SELECT TO authenticated
  USING (
    (
      trading_account_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.trading_accounts ta
        WHERE ta.id = signals.trading_account_id
          AND ta.user_id = public.current_app_user_id()
      )
    )
    OR (
      strategy_metadata_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.strategy_metadata sm
        WHERE sm.id = signals.strategy_metadata_id
          AND sm.owner_user_id = public.current_app_user_id()
      )
    )
  );

CREATE POLICY signals_insert_own
  ON public.signals FOR INSERT TO authenticated
  WITH CHECK (
    trading_account_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

CREATE POLICY signals_update_own
  ON public.signals FOR UPDATE TO authenticated
  USING (
    trading_account_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = signals.trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  )
  WITH CHECK (
    trading_account_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.trading_accounts ta
      WHERE ta.id = trading_account_id
        AND ta.user_id = public.current_app_user_id()
    )
  );

-- ---------------------------------------------------------------------------
-- audit_logs: actors may read their own rows; insert allowed for authenticated
-- ---------------------------------------------------------------------------
CREATE POLICY audit_logs_select_own
  ON public.audit_logs FOR SELECT TO authenticated
  USING (actor_user_id = public.current_app_user_id());

CREATE POLICY audit_logs_insert_authenticated
  ON public.audit_logs FOR INSERT TO authenticated
  WITH CHECK (
    actor_user_id IS NULL
    OR actor_user_id = public.current_app_user_id()
  );

-- service_role bypasses RLS by default in Supabase (backend / migrations).
