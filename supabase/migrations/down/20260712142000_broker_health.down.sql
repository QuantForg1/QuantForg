-- Down: 20260712142000_broker_health

DROP TRIGGER IF EXISTS broker_connection_health_set_updated_at
  ON public.broker_connection_health;
DROP TABLE IF EXISTS public.broker_connection_health CASCADE;

ALTER TABLE public.broker_capabilities
  DROP CONSTRAINT IF EXISTS broker_capabilities_code_check;

ALTER TABLE public.broker_capabilities
  ADD CONSTRAINT broker_capabilities_code_check
  CHECK (code IN (
    'connect', 'disconnect', 'validate', 'refresh',
    'account_info', 'symbols', 'balances', 'positions', 'orders'
  ));

ALTER TABLE public.broker_credentials
  DROP CONSTRAINT IF EXISTS broker_credentials_encryption_key_version_check;
ALTER TABLE public.broker_credentials
  DROP COLUMN IF EXISTS encryption_key_version;
