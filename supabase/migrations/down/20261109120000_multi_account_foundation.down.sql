-- Down: 20261109120000_multi_account_foundation

DROP TRIGGER IF EXISTS account_execution_intents_set_updated_at
  ON public.account_execution_intents;
DROP TABLE IF EXISTS public.account_execution_intents CASCADE;

DROP TRIGGER IF EXISTS central_signals_set_updated_at ON public.central_signals;
DROP TABLE IF EXISTS public.central_signals CASCADE;

DROP TRIGGER IF EXISTS execution_workers_set_updated_at ON public.execution_workers;
DROP TABLE IF EXISTS public.execution_workers CASCADE;

DROP TRIGGER IF EXISTS user_risk_settings_set_updated_at ON public.user_risk_settings;
DROP TABLE IF EXISTS public.user_risk_settings CASCADE;

DROP TRIGGER IF EXISTS platform_risk_policy_set_updated_at ON public.platform_risk_policy;
DROP TABLE IF EXISTS public.platform_risk_policy CASCADE;

DROP INDEX IF EXISTS public.broker_accounts_one_active_per_user_uidx;
DROP INDEX IF EXISTS public.broker_accounts_global_active_claim_uidx;

ALTER TABLE public.broker_accounts
  DROP COLUMN IF EXISTS ownership_verified_at;

ALTER TABLE public.broker_accounts
  DROP COLUMN IF EXISTS ownership_verified;
