-- =============================================================================
-- QuantForg migration: Risk Engine RLS
-- Version: 20260712149100
-- Reversible: see supabase/migrations/down/20260712149100_risk_engine_rls.down.sql
-- Depends on: 20260712149000_risk_engine
-- =============================================================================

ALTER TABLE public.risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_assessments FORCE ROW LEVEL SECURITY;

CREATE POLICY risk_assessments_select_own ON public.risk_assessments
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY risk_assessments_insert_own ON public.risk_assessments
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
