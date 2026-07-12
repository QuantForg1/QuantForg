-- Down: 20260712148100_execution_gateway_rls
DROP POLICY IF EXISTS execution_attempts_insert_own ON public.execution_attempts;
DROP POLICY IF EXISTS execution_attempts_select_own ON public.execution_attempts;
ALTER TABLE public.execution_attempts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.execution_attempts DISABLE ROW LEVEL SECURITY;
