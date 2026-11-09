-- =============================================================================
-- QuantForg: MT5 broker verification evidence (Exness / HFM / multi-broker)
-- Version: 20261109193000
--
-- Additive. Records Windows worker demo/live verification outcomes.
-- Passwords/credentials are NEVER stored.
-- Does NOT enable MULTI_ACCOUNT LIVE submit.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.mt5_broker_verification_evidence (
  broker_slug        text PRIMARY KEY,
  connectable        boolean NOT NULL DEFAULT false,
  connection_status  text NOT NULL DEFAULT 'not_verified',
  evidence           jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_error         text NOT NULL DEFAULT '',
  created_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_broker_ver_slug_nonempty
    CHECK (length(trim(broker_slug)) > 0),
  CONSTRAINT mt5_broker_ver_status_check
    CHECK (connection_status IN (
      'not_verified', 'demo_verified', 'live_verified', 'production_verified'
    ))
);

DROP TRIGGER IF EXISTS mt5_broker_ver_set_updated_at
  ON public.mt5_broker_verification_evidence;
CREATE TRIGGER mt5_broker_ver_set_updated_at
  BEFORE UPDATE ON public.mt5_broker_verification_evidence
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.mt5_broker_verification_evidence IS
  'Windows MT5 broker verification evidence. No passwords. Gates connectable.';

ALTER TABLE public.mt5_broker_verification_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_broker_verification_evidence FORCE ROW LEVEL SECURITY;
