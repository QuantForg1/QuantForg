-- Down: 20260712151100_backtest_engine_rls
DROP POLICY IF EXISTS backtest_equity_curves_insert_own ON public.backtest_equity_curves;
DROP POLICY IF EXISTS backtest_equity_curves_select_own ON public.backtest_equity_curves;
DROP POLICY IF EXISTS backtest_metrics_insert_own ON public.backtest_metrics;
DROP POLICY IF EXISTS backtest_metrics_select_own ON public.backtest_metrics;
DROP POLICY IF EXISTS backtest_trades_insert_own ON public.backtest_trades;
DROP POLICY IF EXISTS backtest_trades_select_own ON public.backtest_trades;
DROP POLICY IF EXISTS backtest_runs_insert_own ON public.backtest_runs;
DROP POLICY IF EXISTS backtest_runs_select_own ON public.backtest_runs;

ALTER TABLE IF EXISTS public.backtest_equity_curves DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.backtest_metrics DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.backtest_trades DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.backtest_runs DISABLE ROW LEVEL SECURITY;
