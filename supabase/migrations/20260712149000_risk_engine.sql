-- =============================================================================
-- QuantForg migration: Risk Management Engine (assessments / history)
-- Version: 20260712149000
-- Reversible: see supabase/migrations/down/20260712149000_risk_engine.down.sql
-- Depends on: users
-- NOTE: Risk assessments only — no credentials, no execution, no order_send.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.risk_assessments (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  decision            text NOT NULL CHECK (decision IN ('allow', 'reduce_size', 'reject')),
  risk_score          integer NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
  risk_band           text NOT NULL CHECK (risk_band IN ('low', 'medium', 'high', 'blocked')),
  approved_lots       text NOT NULL,
  requested_lots      text NOT NULL,
  sizing_method       text NOT NULL DEFAULT 'percentage_risk',
  warnings            jsonb NOT NULL DEFAULT '[]'::jsonb,
  reasons             jsonb NOT NULL DEFAULT '[]'::jsonb,
  exposure            jsonb NOT NULL DEFAULT '{}'::jsonb,
  drawdown            jsonb NOT NULL DEFAULT '{}'::jsonb,
  checks              jsonb NOT NULL DEFAULT '{}'::jsonb,
  request_snapshot    jsonb NOT NULL DEFAULT '{}'::jsonb,
  assessed_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT risk_assessments_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT risk_assessments_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS risk_assessments_user_id_idx
  ON public.risk_assessments (user_id);
CREATE INDEX IF NOT EXISTS risk_assessments_assessed_at_idx
  ON public.risk_assessments (assessed_at DESC);
CREATE INDEX IF NOT EXISTS risk_assessments_decision_idx
  ON public.risk_assessments (decision);
CREATE INDEX IF NOT EXISTS risk_assessments_user_request_idx
  ON public.risk_assessments (user_id, request_id);

COMMENT ON TABLE public.risk_assessments IS
  'Risk Management Engine assessments (ALLOW/REDUCE_SIZE/REJECT). No execution.';
