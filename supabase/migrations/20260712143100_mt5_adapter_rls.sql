-- =============================================================================
-- QuantForg migration: MT5 Adapter RLS
-- Version: 20260712143100
-- Reversible: see supabase/migrations/down/20260712143100_mt5_adapter_rls.down.sql
-- Depends on: 20260712143000_mt5_adapter, public.current_app_user_id
-- =============================================================================

ALTER TABLE public.mt5_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_connections FORCE ROW LEVEL SECURITY;

CREATE POLICY mt5_connections_select_own ON public.mt5_connections
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY mt5_connections_insert_own ON public.mt5_connections
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY mt5_connections_update_own ON public.mt5_connections
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY mt5_connections_delete_own ON public.mt5_connections
  FOR DELETE TO authenticated
  USING (user_id = public.current_app_user_id());

ALTER TABLE public.mt5_connection_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_connection_events FORCE ROW LEVEL SECURITY;

CREATE POLICY mt5_connection_events_select_own ON public.mt5_connection_events
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY mt5_connection_events_insert_own ON public.mt5_connection_events
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());
