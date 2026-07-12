-- Down: 20260712154100_operations_platform_rls
DROP POLICY IF EXISTS health_history_insert_authenticated ON public.health_history;
DROP POLICY IF EXISTS health_history_select_authenticated ON public.health_history;
DROP POLICY IF EXISTS system_metrics_insert_authenticated ON public.system_metrics;
DROP POLICY IF EXISTS system_metrics_select_authenticated ON public.system_metrics;
DROP POLICY IF EXISTS system_alerts_update_authenticated ON public.system_alerts;
DROP POLICY IF EXISTS system_alerts_insert_authenticated ON public.system_alerts;
DROP POLICY IF EXISTS system_alerts_select_authenticated ON public.system_alerts;

ALTER TABLE public.health_history NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.system_metrics NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.system_alerts NO FORCE ROW LEVEL SECURITY;

ALTER TABLE public.health_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_metrics DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_alerts DISABLE ROW LEVEL SECURITY;
