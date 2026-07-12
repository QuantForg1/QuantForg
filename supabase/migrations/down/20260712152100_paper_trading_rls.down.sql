-- Down: 20260712152100_paper_trading_rls
DROP POLICY IF EXISTS paper_performance_update_own ON public.paper_performance;
DROP POLICY IF EXISTS paper_performance_insert_own ON public.paper_performance;
DROP POLICY IF EXISTS paper_performance_select_own ON public.paper_performance;
DROP POLICY IF EXISTS paper_trades_insert_own ON public.paper_trades;
DROP POLICY IF EXISTS paper_trades_select_own ON public.paper_trades;
DROP POLICY IF EXISTS paper_positions_update_own ON public.paper_positions;
DROP POLICY IF EXISTS paper_positions_insert_own ON public.paper_positions;
DROP POLICY IF EXISTS paper_positions_select_own ON public.paper_positions;
DROP POLICY IF EXISTS paper_orders_insert_own ON public.paper_orders;
DROP POLICY IF EXISTS paper_orders_select_own ON public.paper_orders;
DROP POLICY IF EXISTS paper_portfolios_update_own ON public.paper_portfolios;
DROP POLICY IF EXISTS paper_portfolios_insert_own ON public.paper_portfolios;
DROP POLICY IF EXISTS paper_portfolios_select_own ON public.paper_portfolios;

ALTER TABLE IF EXISTS public.paper_performance DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_trades DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_positions DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_orders DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.paper_portfolios DISABLE ROW LEVEL SECURITY;
