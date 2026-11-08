ALTER TABLE public.billing_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contact_leads ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.billing_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE public.billing_webhook_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.contact_leads FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_orders_select_own ON public.billing_orders;
CREATE POLICY billing_orders_select_own
  ON public.billing_orders FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

DROP POLICY IF EXISTS billing_webhook_events_deny_authenticated ON public.billing_webhook_events;
CREATE POLICY billing_webhook_events_deny_authenticated
  ON public.billing_webhook_events FOR SELECT TO authenticated
  USING (false);

DROP POLICY IF EXISTS contact_leads_deny_authenticated_select ON public.contact_leads;
CREATE POLICY contact_leads_deny_authenticated_select
  ON public.contact_leads FOR SELECT TO authenticated
  USING (false);

DROP POLICY IF EXISTS contact_leads_deny_authenticated_insert ON public.contact_leads;
CREATE POLICY contact_leads_deny_authenticated_insert
  ON public.contact_leads FOR INSERT TO authenticated
  WITH CHECK (false);

GRANT SELECT ON public.billing_orders TO authenticated;
GRANT ALL ON public.billing_orders TO service_role;
GRANT ALL ON public.billing_webhook_events TO service_role;
GRANT ALL ON public.contact_leads TO service_role;;
