-- =============================================================================
-- QuantForg migration: MT5 Adapter Sprint 4 (execution gateway attempts)
-- Version: 20260712148000
-- Reversible: see supabase/migrations/down/20260712148000_execution_gateway.down.sql
-- Depends on: users
-- NOTE: Execution requests/results only — no credentials. Flag-gated in app.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.execution_attempts (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL DEFAULT 'market',
  volume              text NOT NULL,
  outcome             text NOT NULL CHECK (
    outcome IN ('success', 'failed', 'disabled', 'retry', 'cancelled', 'prepared')
  ),
  retcode             integer NOT NULL DEFAULT 0,
  message             text NOT NULL DEFAULT '',
  order_ticket        bigint,
  deal_ticket         bigint,
  price               text NOT NULL DEFAULT '0',
  retryable           boolean NOT NULL DEFAULT false,
  request_snapshot    jsonb NOT NULL DEFAULT '{}'::jsonb,
  result_snapshot     jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotent_replay   boolean NOT NULL DEFAULT false,
  submitted_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT execution_attempts_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT execution_attempts_symbol_nonempty CHECK (length(trim(symbol)) > 0),
  CONSTRAINT execution_attempts_volume_nonempty CHECK (length(trim(volume)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS execution_attempts_user_request_uidx
  ON public.execution_attempts (user_id, request_id)
  WHERE idempotent_replay = false;

CREATE INDEX IF NOT EXISTS execution_attempts_user_id_idx
  ON public.execution_attempts (user_id);
CREATE INDEX IF NOT EXISTS execution_attempts_submitted_at_idx
  ON public.execution_attempts (submitted_at DESC);
CREATE INDEX IF NOT EXISTS execution_attempts_outcome_idx
  ON public.execution_attempts (outcome);

COMMENT ON TABLE public.execution_attempts IS
  'Execution Gateway requests/results (Sprint 4). No credentials. Disabled by default.';
