-- =============================================================================
-- QuantForg migration: Execution Audits RLS
-- Version: 20260720190100
-- Reversible: see supabase/migrations/down/20260720190100_execution_audits_rls.down.sql
-- Depends on: 20260720190000_execution_audits
-- =============================================================================

ALTER TABLE public.execution_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_audits FORCE ROW LEVEL SECURITY;

CREATE POLICY execution_audits_select_own ON public.execution_audits
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY execution_audits_insert_own ON public.execution_audits
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete — immutable audit history from client role
