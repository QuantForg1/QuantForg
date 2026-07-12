-- Down: 20260712140000_broker_foundation
-- Drop children first, then catalogue column extensions.

DROP TRIGGER IF EXISTS broker_connections_set_updated_at ON public.broker_connections;
DROP TABLE IF EXISTS public.broker_connections CASCADE;

DROP TRIGGER IF EXISTS broker_credentials_set_updated_at ON public.broker_credentials;
DROP TABLE IF EXISTS public.broker_credentials CASCADE;

DROP TRIGGER IF EXISTS broker_accounts_set_updated_at ON public.broker_accounts;
DROP TABLE IF EXISTS public.broker_accounts CASCADE;

DROP TRIGGER IF EXISTS broker_capabilities_set_updated_at ON public.broker_capabilities;
DROP TABLE IF EXISTS public.broker_capabilities CASCADE;

DROP INDEX IF EXISTS brokers_platform_code_idx;

ALTER TABLE public.brokers DROP COLUMN IF EXISTS description;
ALTER TABLE public.brokers DROP COLUMN IF EXISTS platform_code;
