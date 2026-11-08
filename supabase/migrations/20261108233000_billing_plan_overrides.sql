-- =============================================================================
-- QuantForg: admin-editable plan catalog overlays (prices, active, intervals)
-- Additive only. Canonical plan_ids remain starter/professional/premium.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.billing_plan_overrides (
  plan_id            text PRIMARY KEY
                       CHECK (plan_id IN ('starter', 'professional', 'premium')),
  active             boolean NOT NULL DEFAULT true,
  monthly_price_usd  numeric(12, 2),
  annual_price_usd   numeric(12, 2),
  billing_interval   text NOT NULL DEFAULT 'monthly'
                       CHECK (billing_interval IN ('monthly', 'annual', 'both')),
  trial_days         integer
                       CHECK (trial_days IS NULL OR (trial_days >= 0 AND trial_days <= 90)),
  positioning        text,
  entitlements       jsonb,
  grace_period_days  integer NOT NULL DEFAULT 3
                       CHECK (grace_period_days >= 0 AND grace_period_days <= 30),
  updated_by         uuid REFERENCES public.users (id) ON DELETE SET NULL,
  updated_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at         timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS billing_plan_overrides_active_idx
  ON public.billing_plan_overrides (active);

COMMENT ON TABLE public.billing_plan_overrides IS
  'Owner/admin overlays for SaaS plan pricing and availability. Code catalog remains fallback.';

ALTER TABLE public.billing_plan_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_plan_overrides FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_plan_overrides_deny_authenticated
  ON public.billing_plan_overrides;
CREATE POLICY billing_plan_overrides_deny_authenticated
  ON public.billing_plan_overrides
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

GRANT SELECT ON public.billing_plan_overrides TO authenticated;
GRANT ALL ON public.billing_plan_overrides TO service_role;
