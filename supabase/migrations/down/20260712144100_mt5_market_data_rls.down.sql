-- Down: 20260712144100_mt5_market_data_rls

DROP POLICY IF EXISTS mt5_symbol_cache_delete_own ON public.mt5_symbol_cache;
DROP POLICY IF EXISTS mt5_symbol_cache_update_own ON public.mt5_symbol_cache;
DROP POLICY IF EXISTS mt5_symbol_cache_insert_own ON public.mt5_symbol_cache;
DROP POLICY IF EXISTS mt5_symbol_cache_select_own ON public.mt5_symbol_cache;
ALTER TABLE public.mt5_symbol_cache NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_symbol_cache DISABLE ROW LEVEL SECURITY;
