-- Supabase advisor: function_search_path_mutable.
ALTER FUNCTION public.forbid_self_service_role_change() SET search_path = public, pg_temp;
