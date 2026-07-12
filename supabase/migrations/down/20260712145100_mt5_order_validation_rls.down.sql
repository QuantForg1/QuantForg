-- Down: 20260712145100_mt5_order_validation_rls

DROP POLICY IF EXISTS mt5_order_validations_insert_own ON public.mt5_order_validations;
DROP POLICY IF EXISTS mt5_order_validations_select_own ON public.mt5_order_validations;
ALTER TABLE public.mt5_order_validations NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_order_validations DISABLE ROW LEVEL SECURITY;
