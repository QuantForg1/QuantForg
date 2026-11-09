-- Down: 20261109120100_multi_account_foundation_rls

DROP POLICY IF EXISTS account_execution_intents_deny_delete ON public.account_execution_intents;
DROP POLICY IF EXISTS account_execution_intents_deny_update ON public.account_execution_intents;
DROP POLICY IF EXISTS account_execution_intents_deny_write ON public.account_execution_intents;
DROP POLICY IF EXISTS account_execution_intents_select_own ON public.account_execution_intents;

DROP POLICY IF EXISTS central_signals_deny_authenticated ON public.central_signals;
DROP POLICY IF EXISTS execution_workers_deny_authenticated ON public.execution_workers;

DROP POLICY IF EXISTS user_risk_settings_delete_own ON public.user_risk_settings;
DROP POLICY IF EXISTS user_risk_settings_update_own ON public.user_risk_settings;
DROP POLICY IF EXISTS user_risk_settings_insert_own ON public.user_risk_settings;
DROP POLICY IF EXISTS user_risk_settings_select_own ON public.user_risk_settings;

DROP POLICY IF EXISTS platform_risk_policy_select_authenticated ON public.platform_risk_policy;
