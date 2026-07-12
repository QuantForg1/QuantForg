-- =============================================================================
-- QuantForg migration: MT5 order validation RLS
-- Version: 20260712145100
-- Reversible: see supabase/migrations/down/20260712145100_mt5_order_validation_rls.down.sql
-- Depends on: 20260712145000_mt5_order_validation
-- =============================================================================

ALTER TABLE public.mt5_order_validations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_order_validations FORCE ROW LEVEL SECURITY;

CREATE POLICY mt5_order_validations_select_own ON public.mt5_order_validations
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY mt5_order_validations_insert_own ON public.mt5_order_validations
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- No update/delete for audit-style history (immutable from client role)
