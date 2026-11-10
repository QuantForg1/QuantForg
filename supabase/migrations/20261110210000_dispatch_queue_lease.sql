-- Phase 6.1 — durable dispatch queue lease / delivery columns.
-- Extends account_execution_intents; does NOT enable LIVE multi-account submit.
-- No plaintext credentials may be stored in payload.

ALTER TABLE public.account_execution_intents
  ADD COLUMN IF NOT EXISTS lease_owner_worker_id uuid
    REFERENCES public.execution_workers (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS available_at timestamptz
    NOT NULL DEFAULT timezone('utc', now()),
  ADD COLUMN IF NOT EXISTS delivery_status text NOT NULL DEFAULT 'none'
    CHECK (delivery_status IN (
      'none', 'pending', 'claimed', 'delivered', 'acked',
      'failed', 'expired', 'cancelled', 'dead_letter'
    )),
  ADD COLUMN IF NOT EXISTS delivered_at timestamptz,
  ADD COLUMN IF NOT EXISTS acked_at timestamptz,
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 5
    CHECK (max_attempts BETWEEN 1 AND 50),
  ADD COLUMN IF NOT EXISTS next_retry_at timestamptz,
  ADD COLUMN IF NOT EXISTS kill_switch boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.account_execution_intents.delivery_status IS
  'Worker delivery lifecycle (orthogonal to AccountExecutionState). LIVE submit stays gated.';

CREATE INDEX IF NOT EXISTS account_execution_intents_claim_idx
  ON public.account_execution_intents (state, delivery_status, available_at)
  WHERE state = 'queued'
    AND delivery_status IN ('pending', 'claimed', 'failed')
    AND kill_switch = false;

CREATE INDEX IF NOT EXISTS account_execution_intents_lease_idx
  ON public.account_execution_intents (lease_owner_worker_id, lease_expires_at)
  WHERE lease_owner_worker_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.dispatch_delivery_events (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  intent_id               uuid NOT NULL
                            REFERENCES public.account_execution_intents (id) ON DELETE CASCADE,
  user_id                 uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_account_id       uuid NOT NULL REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  worker_id               uuid REFERENCES public.execution_workers (id) ON DELETE SET NULL,
  event_type              text NOT NULL
                            CHECK (event_type IN (
                              'enqueued', 'claimed', 'delivered', 'acked',
                              'failed', 'expired', 'cancelled', 'dead_letter',
                              'lease_released', 'restart_recovered'
                            )),
  detail                  text NOT NULL DEFAULT '',
  metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at              timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT dispatch_delivery_events_no_secrets
    CHECK (
      NOT (metadata ? 'password')
      AND NOT (metadata ? 'token')
      AND NOT (metadata ? 'sealed_credentials')
    )
);

CREATE INDEX IF NOT EXISTS dispatch_delivery_events_intent_idx
  ON public.dispatch_delivery_events (intent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dispatch_delivery_events_user_idx
  ON public.dispatch_delivery_events (user_id, created_at DESC);

COMMENT ON TABLE public.dispatch_delivery_events IS
  'Audit trail for multi-account dispatch delivery. Never stores credentials. LIVE submit remains off.';
