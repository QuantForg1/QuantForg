-- Down: 20260712143000_mt5_adapter

DROP TABLE IF EXISTS public.mt5_connection_events CASCADE;
DROP TRIGGER IF EXISTS mt5_connections_set_updated_at ON public.mt5_connections;
DROP TABLE IF EXISTS public.mt5_connections CASCADE;
