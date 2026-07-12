-- =============================================================================
-- QuantForg migration: Walk-Forward Validation RLS
-- Version: 20260712153100
-- Reversible: see supabase/migrations/down/20260712153100_walkforward_rls.down.sql
-- Depends on: 20260712153000_walkforward
-- =============================================================================

ALTER TABLE public.walkforward_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.walkforward_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY walkforward_runs_select_own ON public.walkforward_runs
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY walkforward_runs_insert_own ON public.walkforward_runs
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.walkforward_oos_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.walkforward_oos_metrics FORCE ROW LEVEL SECURITY;

CREATE POLICY walkforward_oos_metrics_select_own ON public.walkforward_oos_metrics
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY walkforward_oos_metrics_insert_own ON public.walkforward_oos_metrics
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

ALTER TABLE public.walkforward_robustness_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.walkforward_robustness_reports FORCE ROW LEVEL SECURITY;

CREATE POLICY walkforward_robustness_select_own ON public.walkforward_robustness_reports
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY walkforward_robustness_insert_own ON public.walkforward_robustness_reports
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
