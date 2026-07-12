-- Down: 20260712149100_risk_engine_rls
DROP POLICY IF EXISTS risk_assessments_insert_own ON public.risk_assessments;
DROP POLICY IF EXISTS risk_assessments_select_own ON public.risk_assessments;
ALTER TABLE public.risk_assessments NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.risk_assessments DISABLE ROW LEVEL SECURITY;
