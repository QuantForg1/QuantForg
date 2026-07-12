-- Down: 20260712143100_mt5_adapter_rls

DROP POLICY IF EXISTS mt5_connection_events_insert_own
  ON public.mt5_connection_events;
DROP POLICY IF EXISTS mt5_connection_events_select_own
  ON public.mt5_connection_events;
ALTER TABLE public.mt5_connection_events NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_connection_events DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mt5_connections_delete_own ON public.mt5_connections;
DROP POLICY IF EXISTS mt5_connections_update_own ON public.mt5_connections;
DROP POLICY IF EXISTS mt5_connections_insert_own ON public.mt5_connections;
DROP POLICY IF EXISTS mt5_connections_select_own ON public.mt5_connections;
ALTER TABLE public.mt5_connections NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_connections DISABLE ROW LEVEL SECURITY;
