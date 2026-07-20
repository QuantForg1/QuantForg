-- Rollback: restore broader EXECUTE (pre-RC1 hardening posture).
GRANT EXECUTE ON FUNCTION public.rls_auto_enable() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_app_user_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_org_admin(uuid) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_org_member(uuid) TO PUBLIC;
