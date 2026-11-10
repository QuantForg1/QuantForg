-- Phase 6.1 — RLS for dispatch_delivery_events.
-- Owners read own events; writes via service_role only.

ALTER TABLE public.dispatch_delivery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispatch_delivery_events FORCE ROW LEVEL SECURITY;

CREATE POLICY dispatch_delivery_events_select_own
  ON public.dispatch_delivery_events FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

CREATE POLICY dispatch_delivery_events_deny_write
  ON public.dispatch_delivery_events
  FOR INSERT TO authenticated
  WITH CHECK (false);

CREATE POLICY dispatch_delivery_events_deny_update
  ON public.dispatch_delivery_events
  FOR UPDATE TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY dispatch_delivery_events_deny_delete
  ON public.dispatch_delivery_events
  FOR DELETE TO authenticated
  USING (false);

REVOKE ALL ON TABLE public.dispatch_delivery_events FROM anon;
GRANT SELECT ON TABLE public.dispatch_delivery_events TO authenticated;
GRANT ALL ON TABLE public.dispatch_delivery_events TO service_role;
