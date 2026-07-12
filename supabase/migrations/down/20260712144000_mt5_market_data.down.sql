-- Down: 20260712144000_mt5_market_data

DROP TRIGGER IF EXISTS mt5_symbol_cache_set_updated_at ON public.mt5_symbol_cache;
DROP TABLE IF EXISTS public.mt5_symbol_cache CASCADE;
