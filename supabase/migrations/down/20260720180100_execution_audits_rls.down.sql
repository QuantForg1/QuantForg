-- Down: 20260720180100_execution_audits_rls
DROP POLICY IF EXISTS execution_audits_insert_own ON public.execution_audits;
DROP POLICY IF EXISTS execution_audits_select_own ON public.execution_audits;
ALTER TABLE public.execution_audits NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.execution_audits DISABLE ROW LEVEL SECURITY;
