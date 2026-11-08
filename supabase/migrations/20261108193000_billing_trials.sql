-- =============================================================================
-- QuantForg SaaS: free trial eligibility + invoice number helper columns
-- Version: 20261108193000
-- One 7-day Starter trial per customer. No trading-table changes.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.billing_trials (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  email_norm      text NOT NULL,
  plan_id         text NOT NULL DEFAULT 'starter'
                    CHECK (plan_id = 'starter'),
  status          text NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'expired', 'converted', 'cancelled')),
  started_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  expires_at      timestamptz NOT NULL,
  converted_at    timestamptz,
  cancelled_at    timestamptz,
  license_id      uuid REFERENCES public.licenses (id) ON DELETE SET NULL,
  source_ip       text NOT NULL DEFAULT '',
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT billing_trials_email_nonempty CHECK (length(trim(email_norm)) > 0)
);

-- One trial claim per authenticated user.
CREATE UNIQUE INDEX IF NOT EXISTS billing_trials_user_uidx
  ON public.billing_trials (user_id);

-- Soft abuse guard: one trial per normalized email identity.
CREATE UNIQUE INDEX IF NOT EXISTS billing_trials_email_uidx
  ON public.billing_trials (email_norm);

CREATE INDEX IF NOT EXISTS billing_trials_expires_at_idx
  ON public.billing_trials (expires_at);

CREATE TRIGGER billing_trials_set_updated_at
  BEFORE UPDATE ON public.billing_trials
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.billing_trials IS
  'One 7-day Starter free trial per customer identity. No automatic charges.';

ALTER TABLE public.billing_orders
  ADD COLUMN IF NOT EXISTS invoice_number text,
  ADD COLUMN IF NOT EXISTS billing_period_key text,
  ADD COLUMN IF NOT EXISTS reminder_7d_sent_at timestamptz,
  ADD COLUMN IF NOT EXISTS reminder_3d_sent_at timestamptz,
  ADD COLUMN IF NOT EXISTS reminder_expiry_sent_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS billing_orders_invoice_number_uidx
  ON public.billing_orders (invoice_number)
  WHERE invoice_number IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS billing_orders_renewal_period_uidx
  ON public.billing_orders (user_id, billing_period_key)
  WHERE billing_period_key IS NOT NULL;

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS trial_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS trial_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS trial_status text;

-- RLS: customers read only their own trial row.
ALTER TABLE public.billing_trials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_trials_select_own ON public.billing_trials;
CREATE POLICY billing_trials_select_own
  ON public.billing_trials
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- No direct customer INSERT/UPDATE/DELETE — service role / backend only.
