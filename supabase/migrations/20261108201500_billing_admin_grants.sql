-- =============================================================================
-- QuantForg SaaS: admin grants audit + email notification ledger + trial harden
-- Version: 20261108201500
-- Safe additive migration. No drops of customer data.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.billing_admin_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id   uuid REFERENCES public.users (id) ON DELETE SET NULL,
  target_user_id  uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  target_email    text NOT NULL,
  action          text NOT NULL
                    CHECK (action IN (
                      'owner_compensation_premium_grant',
                      'manual_license_adjust',
                      'trial_force_expire',
                      'subscription_force_expire'
                    )),
  reason          text NOT NULL,
  plan_id         text,
  license_tier    text,
  details         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT billing_admin_events_reason_nonempty CHECK (length(trim(reason)) > 0),
  CONSTRAINT billing_admin_events_email_nonempty CHECK (length(trim(target_email)) > 0)
);

CREATE INDEX IF NOT EXISTS billing_admin_events_target_idx
  ON public.billing_admin_events (target_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS billing_admin_events_action_idx
  ON public.billing_admin_events (action, created_at DESC);

COMMENT ON TABLE public.billing_admin_events IS
  'Auditable privileged billing/license mutations (service role / owner only).';

CREATE TABLE IF NOT EXISTS public.billing_email_notifications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  email_norm      text NOT NULL,
  template_key    text NOT NULL,
  dedupe_key      text NOT NULL,
  related_order_id uuid REFERENCES public.billing_orders (id) ON DELETE SET NULL,
  related_trial_id uuid REFERENCES public.billing_trials (id) ON DELETE SET NULL,
  status          text NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
  provider_message_id text,
  error_detail    text NOT NULL DEFAULT '',
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  sent_at         timestamptz,
  CONSTRAINT billing_email_notifications_dedupe_nonempty CHECK (length(trim(dedupe_key)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS billing_email_notifications_dedupe_uidx
  ON public.billing_email_notifications (dedupe_key);

CREATE INDEX IF NOT EXISTS billing_email_notifications_user_idx
  ON public.billing_email_notifications (user_id, created_at DESC);

COMMENT ON TABLE public.billing_email_notifications IS
  'Idempotent ledger for subscription/trial transactional emails.';

ALTER TABLE public.billing_trials
  ADD COLUMN IF NOT EXISTS claim_fingerprint text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS billing_trials_fingerprint_idx
  ON public.billing_trials (claim_fingerprint)
  WHERE length(trim(claim_fingerprint)) > 0;

ALTER TABLE public.billing_trials FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_trials_select_own ON public.billing_trials;
CREATE POLICY billing_trials_select_own
  ON public.billing_trials
  FOR SELECT
  TO authenticated
  USING (user_id = public.current_app_user_id());

ALTER TABLE public.billing_admin_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_admin_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.billing_email_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_email_notifications FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_admin_events_deny_authenticated ON public.billing_admin_events;
CREATE POLICY billing_admin_events_deny_authenticated
  ON public.billing_admin_events
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

DROP POLICY IF EXISTS billing_email_notifications_select_own ON public.billing_email_notifications;
CREATE POLICY billing_email_notifications_select_own
  ON public.billing_email_notifications
  FOR SELECT
  TO authenticated
  USING (user_id = public.current_app_user_id());

GRANT SELECT ON public.billing_trials TO authenticated;
GRANT SELECT ON public.billing_email_notifications TO authenticated;
GRANT ALL ON public.billing_admin_events TO service_role;
GRANT ALL ON public.billing_email_notifications TO service_role;
GRANT ALL ON public.billing_trials TO service_role;
