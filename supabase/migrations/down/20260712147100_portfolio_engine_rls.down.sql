-- Down: 20260712147100_portfolio_engine_rls
DROP POLICY IF EXISTS portfolio_history_cache_insert_own ON public.portfolio_history_cache;
DROP POLICY IF EXISTS portfolio_history_cache_select_own ON public.portfolio_history_cache;
ALTER TABLE public.portfolio_history_cache NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_history_cache DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS portfolio_syncs_insert_own ON public.portfolio_syncs;
DROP POLICY IF EXISTS portfolio_syncs_select_own ON public.portfolio_syncs;
ALTER TABLE public.portfolio_syncs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_syncs DISABLE ROW LEVEL SECURITY;
