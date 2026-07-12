-- =============================================================================
-- QuantForg migration: Strategy Runtime RLS
-- Version: 20260712150100
-- Reversible: see supabase/migrations/down/20260712150100_strategy_runtime_rls.down.sql
-- Depends on: 20260712150000_strategy_runtime
-- =============================================================================

ALTER TABLE public.strategy_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_evaluations FORCE ROW LEVEL SECURITY;

CREATE POLICY strategy_evaluations_select_own ON public.strategy_evaluations
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY strategy_evaluations_insert_own ON public.strategy_evaluations
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.strategy_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_signals FORCE ROW LEVEL SECURITY;

CREATE POLICY strategy_signals_select_own ON public.strategy_signals
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY strategy_signals_insert_own ON public.strategy_signals
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.strategy_decision_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_decision_history FORCE ROW LEVEL SECURITY;

CREATE POLICY strategy_decision_history_select_own ON public.strategy_decision_history
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY strategy_decision_history_insert_own ON public.strategy_decision_history
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
