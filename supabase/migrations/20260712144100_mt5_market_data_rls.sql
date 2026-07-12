-- =============================================================================
-- QuantForg migration: MT5 symbol cache RLS
-- Version: 20260712144100
-- Reversible: see supabase/migrations/down/20260712144100_mt5_market_data_rls.down.sql
-- Depends on: 20260712144000_mt5_market_data
-- =============================================================================

ALTER TABLE public.mt5_symbol_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_symbol_cache FORCE ROW LEVEL SECURITY;

CREATE POLICY mt5_symbol_cache_select_own ON public.mt5_symbol_cache
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY mt5_symbol_cache_insert_own ON public.mt5_symbol_cache
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY mt5_symbol_cache_update_own ON public.mt5_symbol_cache
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY mt5_symbol_cache_delete_own ON public.mt5_symbol_cache
  FOR DELETE TO authenticated
  USING (user_id = public.current_app_user_id());
