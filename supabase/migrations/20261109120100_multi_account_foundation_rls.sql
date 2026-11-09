-- =============================================================================
-- QuantForg: Multi-account foundation RLS (Phase 1)
-- Version: 20261109120100
-- Reversible: see down/20261109120100_multi_account_foundation_rls.down.sql
-- =============================================================================

ALTER TABLE public.platform_risk_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_risk_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.central_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_execution_intents ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.platform_risk_policy FORCE ROW LEVEL SECURITY;
ALTER TABLE public.user_risk_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.execution_workers FORCE ROW LEVEL SECURITY;
ALTER TABLE public.central_signals FORCE ROW LEVEL SECURITY;
ALTER TABLE public.account_execution_intents FORCE ROW LEVEL SECURITY;

-- Platform policy: authenticated may read active policy; writes via service_role only.
CREATE POLICY platform_risk_policy_select_authenticated
  ON public.platform_risk_policy
  FOR SELECT TO authenticated
  USING (is_active = true);

REVOKE ALL ON TABLE public.platform_risk_policy FROM anon;
GRANT SELECT ON TABLE public.platform_risk_policy TO authenticated;
GRANT ALL ON TABLE public.platform_risk_policy TO service_role;

-- User risk settings: owner CRUD on own rows only.
CREATE POLICY user_risk_settings_select_own
  ON public.user_risk_settings FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY user_risk_settings_insert_own
  ON public.user_risk_settings FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY user_risk_settings_update_own
  ON public.user_risk_settings FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY user_risk_settings_delete_own
  ON public.user_risk_settings FOR DELETE TO authenticated
  USING (user_id = public.current_app_user_id());

REVOKE ALL ON TABLE public.user_risk_settings FROM anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_risk_settings TO authenticated;
GRANT ALL ON TABLE public.user_risk_settings TO service_role;

-- Execution workers: no direct customer access (ops via service_role / Admin API).
CREATE POLICY execution_workers_deny_authenticated
  ON public.execution_workers
  FOR ALL TO authenticated
  USING (false)
  WITH CHECK (false);

REVOKE ALL ON TABLE public.execution_workers FROM anon, authenticated;
GRANT ALL ON TABLE public.execution_workers TO service_role;

-- Central signals: no direct customer writes; users may read intents they own via join.
CREATE POLICY central_signals_deny_authenticated
  ON public.central_signals
  FOR ALL TO authenticated
  USING (false)
  WITH CHECK (false);

REVOKE ALL ON TABLE public.central_signals FROM anon, authenticated;
GRANT ALL ON TABLE public.central_signals TO service_role;

-- Account execution intents: owner read-only of own rows.
CREATE POLICY account_execution_intents_select_own
  ON public.account_execution_intents FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY account_execution_intents_deny_write
  ON public.account_execution_intents
  FOR INSERT TO authenticated
  WITH CHECK (false);

CREATE POLICY account_execution_intents_deny_update
  ON public.account_execution_intents
  FOR UPDATE TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY account_execution_intents_deny_delete
  ON public.account_execution_intents
  FOR DELETE TO authenticated
  USING (false);

REVOKE ALL ON TABLE public.account_execution_intents FROM anon;
GRANT SELECT ON TABLE public.account_execution_intents TO authenticated;
GRANT ALL ON TABLE public.account_execution_intents TO service_role;
