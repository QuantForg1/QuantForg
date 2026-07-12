-- Down: 20260712142100_broker_health_rls

DROP POLICY IF EXISTS broker_connection_health_delete_own
  ON public.broker_connection_health;
DROP POLICY IF EXISTS broker_connection_health_update_own
  ON public.broker_connection_health;
DROP POLICY IF EXISTS broker_connection_health_insert_own
  ON public.broker_connection_health;
DROP POLICY IF EXISTS broker_connection_health_select_own
  ON public.broker_connection_health;

ALTER TABLE public.broker_connection_health NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_connection_health DISABLE ROW LEVEL SECURITY;
