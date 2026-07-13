-- Down: 20260713100000_operations_rls_lockdown
DROP POLICY IF EXISTS system_alerts_service_role ON public.system_alerts;
DROP POLICY IF EXISTS system_metrics_service_role ON public.system_metrics;
DROP POLICY IF EXISTS health_history_service_role ON public.health_history;

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

CREATE POLICY system_metrics_select_authenticated ON public.system_metrics
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY system_metrics_insert_authenticated ON public.system_metrics
  FOR INSERT TO authenticated
  WITH CHECK (true);

CREATE POLICY health_history_select_authenticated ON public.health_history
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY health_history_insert_authenticated ON public.health_history
  FOR INSERT TO authenticated
  WITH CHECK (true);
