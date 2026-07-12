-- Down: 20260712140100_broker_foundation_rls

DROP POLICY IF EXISTS broker_connections_delete_own ON public.broker_connections;
DROP POLICY IF EXISTS broker_connections_update_own ON public.broker_connections;
DROP POLICY IF EXISTS broker_connections_insert_own ON public.broker_connections;
DROP POLICY IF EXISTS broker_connections_select_own ON public.broker_connections;

DROP POLICY IF EXISTS broker_credentials_delete_own ON public.broker_credentials;
DROP POLICY IF EXISTS broker_credentials_update_own ON public.broker_credentials;
DROP POLICY IF EXISTS broker_credentials_insert_own ON public.broker_credentials;
DROP POLICY IF EXISTS broker_credentials_select_own ON public.broker_credentials;

DROP POLICY IF EXISTS broker_accounts_delete_own ON public.broker_accounts;
DROP POLICY IF EXISTS broker_accounts_update_own ON public.broker_accounts;
DROP POLICY IF EXISTS broker_accounts_insert_own ON public.broker_accounts;
DROP POLICY IF EXISTS broker_accounts_select_own ON public.broker_accounts;

DROP POLICY IF EXISTS broker_capabilities_select_authenticated
  ON public.broker_capabilities;

ALTER TABLE public.broker_connections NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_credentials NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_accounts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_capabilities NO FORCE ROW LEVEL SECURITY;

ALTER TABLE public.broker_connections DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_credentials DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_accounts DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.broker_capabilities DISABLE ROW LEVEL SECURITY;
