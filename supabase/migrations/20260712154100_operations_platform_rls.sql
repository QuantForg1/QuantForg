-- =============================================================================
-- QuantForg migration: Operations & Observability RLS
-- Version: 20260712154100
-- Reversible: see supabase/migrations/down/20260712154100_operations_platform_rls.down.sql
-- Depends on: 20260712154000_operations_platform
-- =============================================================================

ALTER TABLE public.system_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_alerts FORCE ROW LEVEL SECURITY;

CREATE POLICY system_alerts_select_authenticated ON public.system_alerts
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY system_alerts_insert_authenticated ON public.system_alerts
  FOR INSERT TO authenticated
  WITH CHECK (true);

CREATE POLICY system_alerts_update_authenticated ON public.system_alerts
  FOR UPDATE TO authenticated
  USING (true)
  WITH CHECK (true);

ALTER TABLE public.system_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_metrics FORCE ROW LEVEL SECURITY;

CREATE POLICY system_metrics_select_authenticated ON public.system_metrics
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY system_metrics_insert_authenticated ON public.system_metrics
  FOR INSERT TO authenticated
  WITH CHECK (true);

ALTER TABLE public.health_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_history FORCE ROW LEVEL SECURITY;

CREATE POLICY health_history_select_authenticated ON public.health_history
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY health_history_insert_authenticated ON public.health_history
  FOR INSERT TO authenticated
  WITH CHECK (true);

-- No client deletes (history / metrics append-oriented)
