-- =============================================================================
-- DOWN: 20260712120200_rls_policies
-- Reverses Row Level Security policies and current_app_user_id helper.
-- Safe: drops policies/functions only; does not drop tables or data.
-- =============================================================================

DROP POLICY IF EXISTS audit_logs_insert_authenticated ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_select_own ON public.audit_logs;

DROP POLICY IF EXISTS signals_update_own ON public.signals;
DROP POLICY IF EXISTS signals_insert_own ON public.signals;
DROP POLICY IF EXISTS signals_select_own ON public.signals;

DROP POLICY IF EXISTS trades_insert_own ON public.trades;
DROP POLICY IF EXISTS trades_select_own ON public.trades;

DROP POLICY IF EXISTS positions_update_own ON public.positions;
DROP POLICY IF EXISTS positions_insert_own ON public.positions;
DROP POLICY IF EXISTS positions_select_own ON public.positions;

DROP POLICY IF EXISTS orders_update_own ON public.orders;
DROP POLICY IF EXISTS orders_insert_own ON public.orders;
DROP POLICY IF EXISTS orders_select_own ON public.orders;

DROP POLICY IF EXISTS risk_profiles_delete_own ON public.risk_profiles;
DROP POLICY IF EXISTS risk_profiles_update_own ON public.risk_profiles;
DROP POLICY IF EXISTS risk_profiles_insert_own ON public.risk_profiles;
DROP POLICY IF EXISTS risk_profiles_select_own ON public.risk_profiles;

DROP POLICY IF EXISTS strategy_metadata_delete_own ON public.strategy_metadata;
DROP POLICY IF EXISTS strategy_metadata_update_own ON public.strategy_metadata;
DROP POLICY IF EXISTS strategy_metadata_insert_own ON public.strategy_metadata;
DROP POLICY IF EXISTS strategy_metadata_select_own ON public.strategy_metadata;

DROP POLICY IF EXISTS trading_sessions_update_own ON public.trading_sessions;
DROP POLICY IF EXISTS trading_sessions_insert_own ON public.trading_sessions;
DROP POLICY IF EXISTS trading_sessions_select_own ON public.trading_sessions;

DROP POLICY IF EXISTS trading_accounts_update_own ON public.trading_accounts;
DROP POLICY IF EXISTS trading_accounts_insert_own ON public.trading_accounts;
DROP POLICY IF EXISTS trading_accounts_select_own ON public.trading_accounts;

DROP POLICY IF EXISTS licenses_update_own ON public.licenses;
DROP POLICY IF EXISTS licenses_insert_own ON public.licenses;
DROP POLICY IF EXISTS licenses_select_own ON public.licenses;

DROP POLICY IF EXISTS symbols_select_authenticated ON public.symbols;
DROP POLICY IF EXISTS brokers_select_authenticated ON public.brokers;

DROP POLICY IF EXISTS users_insert_own ON public.users;
DROP POLICY IF EXISTS users_update_own ON public.users;
DROP POLICY IF EXISTS users_select_own ON public.users;

ALTER TABLE public.audit_logs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.signals NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trades NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.positions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.orders NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.risk_profiles NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_metadata NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trading_sessions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.trading_accounts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.symbols NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.licenses NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.brokers NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.users NO FORCE ROW LEVEL SECURITY;

ALTER TABLE public.audit_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.signals DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.trades DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_metadata DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.trading_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.symbols DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.licenses DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.brokers DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;

DROP FUNCTION IF EXISTS public.current_app_user_id();
