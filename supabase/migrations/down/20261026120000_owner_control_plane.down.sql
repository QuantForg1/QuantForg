DROP TRIGGER IF EXISTS users_forbid_self_service_role_change ON public.users;
DROP FUNCTION IF EXISTS public.forbid_self_service_role_change();
DROP TABLE IF EXISTS public.trading_runtime_config;
