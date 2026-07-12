-- Down: 20260712153100_walkforward_rls
DROP POLICY IF EXISTS walkforward_robustness_insert_own ON public.walkforward_robustness_reports;
DROP POLICY IF EXISTS walkforward_robustness_select_own ON public.walkforward_robustness_reports;
DROP POLICY IF EXISTS walkforward_oos_metrics_insert_own ON public.walkforward_oos_metrics;
DROP POLICY IF EXISTS walkforward_oos_metrics_select_own ON public.walkforward_oos_metrics;
DROP POLICY IF EXISTS walkforward_runs_insert_own ON public.walkforward_runs;
DROP POLICY IF EXISTS walkforward_runs_select_own ON public.walkforward_runs;

ALTER TABLE IF EXISTS public.walkforward_robustness_reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.walkforward_oos_metrics DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.walkforward_runs DISABLE ROW LEVEL SECURITY;
