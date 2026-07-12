-- =============================================================================
-- QuantForg migration: Paper Trading RLS
-- Version: 20260712152100
-- Reversible: see supabase/migrations/down/20260712152100_paper_trading_rls.down.sql
-- Depends on: 20260712152000_paper_trading
-- =============================================================================

ALTER TABLE public.paper_portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_portfolios FORCE ROW LEVEL SECURITY;

CREATE POLICY paper_portfolios_select_own ON public.paper_portfolios
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY paper_portfolios_insert_own ON public.paper_portfolios
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY paper_portfolios_update_own ON public.paper_portfolios
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.paper_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_orders FORCE ROW LEVEL SECURITY;

CREATE POLICY paper_orders_select_own ON public.paper_orders
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY paper_orders_insert_own ON public.paper_orders
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.paper_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_positions FORCE ROW LEVEL SECURITY;

CREATE POLICY paper_positions_select_own ON public.paper_positions
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY paper_positions_insert_own ON public.paper_positions
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY paper_positions_update_own ON public.paper_positions
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.paper_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_trades FORCE ROW LEVEL SECURITY;

CREATE POLICY paper_trades_select_own ON public.paper_trades
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY paper_trades_insert_own ON public.paper_trades
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.paper_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_performance FORCE ROW LEVEL SECURITY;

CREATE POLICY paper_performance_select_own ON public.paper_performance
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY paper_performance_insert_own ON public.paper_performance
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY paper_performance_update_own ON public.paper_performance
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());
