-- =============================================================================
-- QuantForg migration: Execution Audit Engine (Phase 11)
-- Version: 20260720190000
-- Reversible: see supabase/migrations/down/20260720190000_execution_audits.down.sql
-- Depends on: users
-- NOTE: Immutable execution-stage history — no credentials. Additive only.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.execution_audits (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id              text NOT NULL,
  stage                   text NOT NULL CHECK (
    stage IN ('validation', 'risk', 'safety', 'submit', 'manage', 'cancel', 'replay')
  ),
  symbol                  text NOT NULL DEFAULT '',
  side                    text NOT NULL DEFAULT '',
  volume                  text NOT NULL DEFAULT '',
  outcome                 text NOT NULL DEFAULT '',
  retcode                 integer NOT NULL DEFAULT 0,
  order_ticket            bigint,
  deal_ticket             bigint,
  latency_ms              double precision,
  gateway_latency_ms      double precision,
  railway_processing_ms   double precision,
  cloudflare_latency_ms   double precision,
  spread                  text,
  slippage                text,
  commission              text,
  swap                    text,
  margin_used             text,
  free_margin             text,
  balance                 text,
  equity                  text,
  leverage                text,
  broker_server_time      text,
  market_session          text,
  execution_route         text NOT NULL DEFAULT 'mt5_gateway',
  payload_in              jsonb NOT NULL DEFAULT '{}'::jsonb,
  payload_out             jsonb NOT NULL DEFAULT '{}'::jsonb,
  related_ids             jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at              timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT execution_audits_request_id_nonempty CHECK (length(trim(request_id)) > 0)
);

CREATE INDEX IF NOT EXISTS execution_audits_user_id_idx
  ON public.execution_audits (user_id);
CREATE INDEX IF NOT EXISTS execution_audits_user_request_idx
  ON public.execution_audits (user_id, request_id);
CREATE INDEX IF NOT EXISTS execution_audits_created_at_idx
  ON public.execution_audits (created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS execution_audits_user_request_stage_uidx
  ON public.execution_audits (user_id, request_id, stage);

COMMENT ON TABLE public.execution_audits IS
  'Execution Audit Engine (Phase 11). Immutable stage history. No credentials.';
