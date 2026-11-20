-- Referral ledger. Client roles cannot read or write these tables.
-- The API uses the database owner. Rewards are not amounts.

CREATE TABLE IF NOT EXISTS public.referral_codes (
  user_id uuid PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
  code text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT referral_codes_code_check CHECK (code ~ '^[A-Z0-9-]{1,32}$')
);

CREATE TABLE IF NOT EXISTS public.referral_attributions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  referred_user_id uuid NOT NULL UNIQUE REFERENCES public.users (id),
  referrer_user_id uuid NOT NULL REFERENCES public.users (id),
  code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT referral_no_self CHECK (referred_user_id <> referrer_user_id)
);

CREATE TABLE IF NOT EXISTS public.referral_events (
  event_key text PRIMARY KEY,
  event_type text NOT NULL,
  referred_user_id uuid REFERENCES public.users (id),
  reward_status text NOT NULL,
  reward_amount numeric,
  reward_currency text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT referral_events_amount_check CHECK (
    reward_amount IS NULL AND reward_currency IS NULL
  ),
  CONSTRAINT referral_events_status_check CHECK (
    reward_status IN ('not_qualified', 'not_issued', 'eligible')
  )
);

CREATE TABLE IF NOT EXISTS public.referral_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  outcome text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS referral_attempts_user_time
  ON public.referral_attempts (user_id, created_at DESC);

ALTER TABLE public.referral_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referral_attributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referral_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referral_attempts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.referral_codes FROM anon, authenticated;
REVOKE ALL ON public.referral_attributions FROM anon, authenticated;
REVOKE ALL ON public.referral_events FROM anon, authenticated;
REVOKE ALL ON public.referral_attempts FROM anon, authenticated;
