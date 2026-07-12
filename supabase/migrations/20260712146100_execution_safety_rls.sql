-- =============================================================================
-- QuantForg migration: Execution Safety RLS
-- Version: 20260712146100
-- Reversible: see supabase/migrations/down/20260712146100_execution_safety_rls.down.sql
-- Depends on: 20260712146000_execution_safety
-- =============================================================================

ALTER TABLE public.execution_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_decisions FORCE ROW LEVEL SECURITY;

CREATE POLICY execution_decisions_select_own ON public.execution_decisions
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY execution_decisions_insert_own ON public.execution_decisions
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
