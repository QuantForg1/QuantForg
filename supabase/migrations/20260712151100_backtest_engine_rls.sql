-- =============================================================================
-- QuantForg migration: Backtesting Engine RLS
-- Version: 20260712151100
-- Reversible: see supabase/migrations/down/20260712151100_backtest_engine_rls.down.sql
-- Depends on: 20260712151000_backtest_engine
-- =============================================================================

ALTER TABLE public.backtest_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY backtest_runs_select_own ON public.backtest_runs
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY backtest_runs_insert_own ON public.backtest_runs
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.backtest_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_trades FORCE ROW LEVEL SECURITY;

CREATE POLICY backtest_trades_select_own ON public.backtest_trades
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY backtest_trades_insert_own ON public.backtest_trades
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.backtest_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_metrics FORCE ROW LEVEL SECURITY;

CREATE POLICY backtest_metrics_select_own ON public.backtest_metrics
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY backtest_metrics_insert_own ON public.backtest_metrics
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.backtest_equity_curves ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backtest_equity_curves FORCE ROW LEVEL SECURITY;

CREATE POLICY backtest_equity_curves_select_own ON public.backtest_equity_curves
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY backtest_equity_curves_insert_own ON public.backtest_equity_curves
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
