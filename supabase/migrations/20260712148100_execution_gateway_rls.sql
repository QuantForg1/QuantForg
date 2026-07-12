-- =============================================================================
-- QuantForg migration: Execution Gateway RLS
-- Version: 20260712148100
-- Reversible: see supabase/migrations/down/20260712148100_execution_gateway_rls.down.sql
-- Depends on: 20260712148000_execution_gateway
-- =============================================================================

ALTER TABLE public.execution_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_attempts FORCE ROW LEVEL SECURITY;

CREATE POLICY execution_attempts_select_own ON public.execution_attempts
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY execution_attempts_insert_own ON public.execution_attempts
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
