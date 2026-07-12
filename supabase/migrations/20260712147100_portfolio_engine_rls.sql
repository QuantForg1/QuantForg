-- =============================================================================
-- QuantForg migration: Portfolio engine RLS
-- Version: 20260712147100
-- Reversible: see supabase/migrations/down/20260712147100_portfolio_engine_rls.down.sql
-- Depends on: 20260712147000_portfolio_engine
-- =============================================================================

ALTER TABLE public.portfolio_syncs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_syncs FORCE ROW LEVEL SECURITY;

CREATE POLICY portfolio_syncs_select_own ON public.portfolio_syncs
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY portfolio_syncs_insert_own ON public.portfolio_syncs
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.portfolio_history_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_history_cache FORCE ROW LEVEL SECURITY;

CREATE POLICY portfolio_history_cache_select_own ON public.portfolio_history_cache
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY portfolio_history_cache_insert_own ON public.portfolio_history_cache
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for cache/history style tables from client role
