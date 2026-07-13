-- =============================================================================
-- QuantForg migration: Lock down Operations RLS (service_role only)
-- Version: 20260713100000
-- Reversible: see supabase/migrations/down/20260713100000_operations_rls_lockdown.down.sql
-- Depends on: 20260712154100_operations_platform_rls
-- =============================================================================
-- Ops tables must not be readable/writable by any authenticated JWT client.
-- The backend uses a privileged DB role (bypasses RLS). PostgREST clients must
-- not access system_alerts / system_metrics / health_history.

DROP POLICY IF EXISTS system_alerts_select_authenticated ON public.system_alerts;
DROP POLICY IF EXISTS system_alerts_insert_authenticated ON public.system_alerts;
DROP POLICY IF EXISTS system_alerts_update_authenticated ON public.system_alerts;

DROP POLICY IF EXISTS system_metrics_select_authenticated ON public.system_metrics;
DROP POLICY IF EXISTS system_metrics_insert_authenticated ON public.system_metrics;

DROP POLICY IF EXISTS health_history_select_authenticated ON public.health_history;
DROP POLICY IF EXISTS health_history_insert_authenticated ON public.health_history;

-- Explicit service_role policies (Supabase dashboard / service key only).
CREATE POLICY system_alerts_service_role ON public.system_alerts
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY system_metrics_service_role ON public.system_metrics
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY health_history_service_role ON public.health_history
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);
