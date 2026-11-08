CREATE TABLE IF NOT EXISTS public.billing_orders (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_code            text NOT NULL,
  user_id               uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  plan_id               text NOT NULL
                          CHECK (plan_id IN ('starter', 'professional', 'premium')),
  license_tier          text NOT NULL
                          CHECK (license_tier IN ('starter', 'professional', 'enterprise')),
  amount_usd            numeric(12, 2) NOT NULL CHECK (amount_usd > 0),
  currency              text NOT NULL DEFAULT 'usd',
  provider              text NOT NULL DEFAULT 'nowpayments',
  provider_invoice_id   text,
  provider_payment_id   text,
  invoice_url           text,
  pay_currency          text,
  status                text NOT NULL DEFAULT 'pending_payment'
                          CHECK (status IN (
                            'pending_payment',
                            'confirming',
                            'partially_paid',
                            'active',
                            'renewal_due',
                            'past_due',
                            'payment_failed',
                            'cancelled',
                            'expired',
                            'suspended',
                            'refunded'
                          )),
  provider_status       text NOT NULL DEFAULT '',
  period_start          timestamptz,
  period_end            timestamptz,
  paid_at               timestamptz,
  cancelled_at          timestamptz,
  expires_at            timestamptz,
  metadata              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT billing_orders_order_code_nonempty CHECK (length(trim(order_code)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS billing_orders_order_code_uidx
  ON public.billing_orders (order_code);
CREATE INDEX IF NOT EXISTS billing_orders_user_id_idx
  ON public.billing_orders (user_id);
CREATE INDEX IF NOT EXISTS billing_orders_status_idx
  ON public.billing_orders (status);
CREATE INDEX IF NOT EXISTS billing_orders_provider_invoice_idx
  ON public.billing_orders (provider_invoice_id)
  WHERE provider_invoice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS billing_orders_provider_payment_idx
  ON public.billing_orders (provider_payment_id)
  WHERE provider_payment_id IS NOT NULL;

CREATE TRIGGER billing_orders_set_updated_at
  BEFORE UPDATE ON public.billing_orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS public.billing_webhook_events (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider          text NOT NULL DEFAULT 'nowpayments',
  event_key         text NOT NULL,
  payment_id        text,
  order_code        text,
  payment_status    text NOT NULL DEFAULT '',
  signature_valid   boolean NOT NULL DEFAULT false,
  processed         boolean NOT NULL DEFAULT false,
  process_result    text NOT NULL DEFAULT '',
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at        timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS billing_webhook_events_event_key_uidx
  ON public.billing_webhook_events (provider, event_key);
CREATE INDEX IF NOT EXISTS billing_webhook_events_order_code_idx
  ON public.billing_webhook_events (order_code)
  WHERE order_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.contact_leads (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name       text NOT NULL,
  email           text NOT NULL,
  company         text NOT NULL DEFAULT '',
  country         text NOT NULL DEFAULT '',
  phone           text NOT NULL DEFAULT '',
  subject         text NOT NULL DEFAULT '',
  message         text NOT NULL,
  plan_intent     text NOT NULL DEFAULT '',
  experience      text NOT NULL DEFAULT '',
  contact_method  text NOT NULL DEFAULT '',
  source_ip       text NOT NULL DEFAULT '',
  user_agent      text NOT NULL DEFAULT '',
  status          text NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'reviewed', 'closed')),
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT contact_leads_name_nonempty CHECK (length(trim(full_name)) > 0),
  CONSTRAINT contact_leads_email_nonempty CHECK (length(trim(email)) > 0),
  CONSTRAINT contact_leads_message_nonempty CHECK (length(trim(message)) > 0)
);

CREATE INDEX IF NOT EXISTS contact_leads_email_idx
  ON public.contact_leads (lower(email));
CREATE INDEX IF NOT EXISTS contact_leads_created_at_idx
  ON public.contact_leads (created_at DESC);

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS subscription_plan_id text,
  ADD COLUMN IF NOT EXISTS subscription_status text,
  ADD COLUMN IF NOT EXISTS subscription_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS subscription_provider text;;
