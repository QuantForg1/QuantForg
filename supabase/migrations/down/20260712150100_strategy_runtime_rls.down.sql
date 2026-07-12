-- Down: 20260712150100_strategy_runtime_rls
DROP POLICY IF EXISTS strategy_decision_history_insert_own ON public.strategy_decision_history;
DROP POLICY IF EXISTS strategy_decision_history_select_own ON public.strategy_decision_history;
DROP POLICY IF EXISTS strategy_signals_insert_own ON public.strategy_signals;
DROP POLICY IF EXISTS strategy_signals_select_own ON public.strategy_signals;
DROP POLICY IF EXISTS strategy_evaluations_insert_own ON public.strategy_evaluations;
DROP POLICY IF EXISTS strategy_evaluations_select_own ON public.strategy_evaluations;

ALTER TABLE IF EXISTS public.strategy_decision_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.strategy_signals DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.strategy_evaluations DISABLE ROW LEVEL SECURITY;
