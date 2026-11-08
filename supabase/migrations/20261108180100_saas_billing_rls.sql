-- =============================================================================
-- RLS for SaaS billing tables
-- Version: 20261108180100
-- =============================================================================

ALTER TABLE public.billing_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contact_leads ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.billing_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE public.billing_webhook_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.contact_leads FORCE ROW LEVEL SECURITY;

-- Customers may read only their own billing orders. Writes via service_role / API.
CREATE POLICY billing_orders_select_own
  ON public.billing_orders FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

-- Webhook events: no authenticated client access (service_role only).
CREATE POLICY billing_webhook_events_deny_authenticated
  ON public.billing_webhook_events FOR SELECT TO authenticated
  USING (false);

-- Contact leads: no customer SELECT (operators use service_role / COP later).
CREATE POLICY contact_leads_deny_authenticated_select
  ON public.contact_leads FOR SELECT TO authenticated
  USING (false);

-- Authenticated insert of own contact lead is not used (API uses service role).
-- Keep inserts closed for JWT clients.
CREATE POLICY contact_leads_deny_authenticated_insert
  ON public.contact_leads FOR INSERT TO authenticated
  WITH CHECK (false);

GRANT SELECT ON public.billing_orders TO authenticated;
GRANT ALL ON public.billing_orders TO service_role;
GRANT ALL ON public.billing_webhook_events TO service_role;
GRANT ALL ON public.contact_leads TO service_role;
