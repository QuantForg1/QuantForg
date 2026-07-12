-- Down: 20260712146100_execution_safety_rls
DROP POLICY IF EXISTS execution_decisions_insert_own ON public.execution_decisions;
DROP POLICY IF EXISTS execution_decisions_select_own ON public.execution_decisions;
ALTER TABLE public.execution_decisions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.execution_decisions DISABLE ROW LEVEL SECURITY;
