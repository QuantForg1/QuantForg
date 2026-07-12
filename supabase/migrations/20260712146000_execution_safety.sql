-- =============================================================================
-- QuantForg migration: Execution Safety Layer (decision history)
-- Version: 20260712146000
-- Reversible: see supabase/migrations/down/20260712146000_execution_safety.down.sql
-- Depends on: users
-- NOTE: Execution decisions only — never stores credentials or live orders.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.execution_decisions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  decision            text NOT NULL CHECK (decision IN ('allow', 'reject', 'retry')),
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL DEFAULT 'market',
  volume              text NOT NULL,
  rejection_reasons   jsonb NOT NULL DEFAULT '[]'::jsonb,
  warnings            jsonb NOT NULL DEFAULT '[]'::jsonb,
  calculated_risk     jsonb NOT NULL DEFAULT '{}'::jsonb,
  checks              jsonb NOT NULL DEFAULT '{}'::jsonb,
  request_fingerprint text NOT NULL DEFAULT '',
  request_snapshot    jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotent_replay   boolean NOT NULL DEFAULT false,
  decided_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT execution_decisions_symbol_nonempty CHECK (length(trim(symbol)) > 0),
  CONSTRAINT execution_decisions_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT execution_decisions_volume_nonempty CHECK (length(trim(volume)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS execution_decisions_user_request_uidx
  ON public.execution_decisions (user_id, request_id)
  WHERE idempotent_replay = false;

CREATE INDEX IF NOT EXISTS execution_decisions_user_id_idx
  ON public.execution_decisions (user_id);
CREATE INDEX IF NOT EXISTS execution_decisions_decided_at_idx
  ON public.execution_decisions (decided_at DESC);
CREATE INDEX IF NOT EXISTS execution_decisions_fingerprint_idx
  ON public.execution_decisions (user_id, request_fingerprint);

COMMENT ON TABLE public.execution_decisions IS
  'Execution safety decisions (ALLOW/REJECT/RETRY). No credentials. No order_send.';
