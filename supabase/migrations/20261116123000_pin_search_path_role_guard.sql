-- Security advisor 0011: pin search_path on the role-change guard trigger.
ALTER FUNCTION public.forbid_self_service_role_change() SET search_path = public, pg_temp;
