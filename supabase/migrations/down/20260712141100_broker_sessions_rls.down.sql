-- Down: 20260712141100_broker_sessions_rls

DROP POLICY IF EXISTS broker_sessions_delete_own ON public.broker_sessions;
DROP POLICY IF EXISTS broker_sessions_update_own ON public.broker_sessions;
DROP POLICY IF EXISTS broker_sessions_insert_own ON public.broker_sessions;
DROP POLICY IF EXISTS broker_sessions_select_own ON public.broker_sessions;

ALTER TABLE public.broker_sessions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.broker_sessions DISABLE ROW LEVEL SECURITY;
