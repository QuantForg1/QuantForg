-- =============================================================================
-- QuantForg migration: User Platform RLS
-- Version: 20260712130100
-- Reversible: see supabase/migrations/down/20260712130100_user_platform_rls.down.sql
-- =============================================================================

-- Helper: is the current app user a member of an organization?
CREATE OR REPLACE FUNCTION public.is_org_member(org_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.organization_members m
    WHERE m.organization_id = org_id
      AND m.user_id = public.current_app_user_id()
      AND m.status = 'active'
  );
$$;

CREATE OR REPLACE FUNCTION public.is_org_admin(org_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.organization_members m
    WHERE m.organization_id = org_id
      AND m.user_id = public.current_app_user_id()
      AND m.status = 'active'
      AND m.role IN ('owner', 'admin')
  );
$$;

REVOKE ALL ON FUNCTION public.is_org_member(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.is_org_admin(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_org_member(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_org_admin(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_org_member(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.is_org_admin(uuid) TO service_role;

-- Enable + force RLS
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activity_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.storage_objects ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.user_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.user_devices FORCE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members FORCE ROW LEVEL SECURITY;
ALTER TABLE public.organization_invitations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.activity_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.notifications FORCE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE public.storage_objects FORCE ROW LEVEL SECURITY;

-- user_profiles: own row only
CREATE POLICY user_profiles_select_own ON public.user_profiles
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY user_profiles_insert_own ON public.user_profiles
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());
CREATE POLICY user_profiles_update_own ON public.user_profiles
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- user_settings: own row only
CREATE POLICY user_settings_select_own ON public.user_settings
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY user_settings_insert_own ON public.user_settings
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());
CREATE POLICY user_settings_update_own ON public.user_settings
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- devices / sessions: own only
CREATE POLICY user_devices_all_own ON public.user_devices
  FOR ALL TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY user_sessions_select_own ON public.user_sessions
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY user_sessions_insert_own ON public.user_sessions
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());
CREATE POLICY user_sessions_update_own ON public.user_sessions
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- organizations: members can read; owners/admins manage
CREATE POLICY organizations_select_member ON public.organizations
  FOR SELECT TO authenticated
  USING (public.is_org_member(id) OR owner_user_id = public.current_app_user_id());
CREATE POLICY organizations_insert_owner ON public.organizations
  FOR INSERT TO authenticated
  WITH CHECK (owner_user_id = public.current_app_user_id());
CREATE POLICY organizations_update_admin ON public.organizations
  FOR UPDATE TO authenticated
  USING (public.is_org_admin(id))
  WITH CHECK (public.is_org_admin(id));

CREATE POLICY organization_members_select ON public.organization_members
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id) OR user_id = public.current_app_user_id());
CREATE POLICY organization_members_insert_admin ON public.organization_members
  FOR INSERT TO authenticated
  WITH CHECK (
    public.is_org_admin(organization_id)
    OR user_id = public.current_app_user_id()
  );
CREATE POLICY organization_members_update_admin ON public.organization_members
  FOR UPDATE TO authenticated
  USING (public.is_org_admin(organization_id) OR user_id = public.current_app_user_id())
  WITH CHECK (public.is_org_admin(organization_id) OR user_id = public.current_app_user_id());

CREATE POLICY organization_invitations_select ON public.organization_invitations
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id));
CREATE POLICY organization_invitations_insert_admin ON public.organization_invitations
  FOR INSERT TO authenticated
  WITH CHECK (public.is_org_admin(organization_id));
CREATE POLICY organization_invitations_update_admin ON public.organization_invitations
  FOR UPDATE TO authenticated
  USING (public.is_org_admin(organization_id))
  WITH CHECK (public.is_org_admin(organization_id));

-- activity: own insert/select; no update/delete policies (triggers block mutations)
CREATE POLICY activity_events_select_own ON public.activity_events
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY activity_events_insert_own ON public.activity_events
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

-- notifications
CREATE POLICY notifications_select_own ON public.notifications
  FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY notifications_update_own ON public.notifications
  FOR UPDATE TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());
CREATE POLICY notifications_insert_own ON public.notifications
  FOR INSERT TO authenticated
  WITH CHECK (user_id = public.current_app_user_id());

CREATE POLICY notification_preferences_all_own ON public.notification_preferences
  FOR ALL TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());

-- storage metadata: own only (bucket policies enforced in Storage separately)
CREATE POLICY storage_objects_all_own ON public.storage_objects
  FOR ALL TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (user_id = public.current_app_user_id());
