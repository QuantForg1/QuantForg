-- =============================================================================
-- QuantForg migration: Strategy Runtime (evaluations / signals / decision history)
-- Version: 20260712150000
-- Reversible: see supabase/migrations/down/20260712150000_strategy_runtime.down.sql
-- Depends on: users
-- NOTE: Strategy decisions only — no credentials, no execution, no order_send.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.strategy_evaluations (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  symbol              text NOT NULL,
  timeframe           text NOT NULL DEFAULT 'm15',
  decision            text NOT NULL CHECK (
    decision IN ('no_action', 'watch', 'ready', 'blocked')
  ),
  reasons             jsonb NOT NULL DEFAULT '[]'::jsonb,
  preconditions       jsonb NOT NULL DEFAULT '{}'::jsonb,
  market_state        jsonb NOT NULL DEFAULT '{}'::jsonb,
  signal_id           uuid,
  risk_decision       text,
  risk_score          integer CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)),
  evaluated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT strategy_evaluations_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT strategy_evaluations_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS strategy_evaluations_user_id_idx
  ON public.strategy_evaluations (user_id);
CREATE INDEX IF NOT EXISTS strategy_evaluations_evaluated_at_idx
  ON public.strategy_evaluations (evaluated_at DESC);
CREATE INDEX IF NOT EXISTS strategy_evaluations_decision_idx
  ON public.strategy_evaluations (decision);
CREATE INDEX IF NOT EXISTS strategy_evaluations_user_request_idx
  ON public.strategy_evaluations (user_id, request_id);

COMMENT ON TABLE public.strategy_evaluations IS
  'Strategy Runtime evaluations (NO_ACTION/WATCH/READY/BLOCKED). No execution.';

CREATE TABLE IF NOT EXISTS public.strategy_signals (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  evaluation_id       uuid REFERENCES public.strategy_evaluations (id) ON DELETE SET NULL,
  symbol              text NOT NULL,
  timeframe           text NOT NULL DEFAULT 'm15',
  direction           text NOT NULL CHECK (direction IN ('buy', 'sell', 'neutral')),
  confidence          double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  reasons             jsonb NOT NULL DEFAULT '[]'::jsonb,
  rejected            boolean NOT NULL DEFAULT false,
  rejection_reasons   jsonb NOT NULL DEFAULT '[]'::jsonb,
  generated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT strategy_signals_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS strategy_signals_user_id_idx
  ON public.strategy_signals (user_id);
CREATE INDEX IF NOT EXISTS strategy_signals_generated_at_idx
  ON public.strategy_signals (generated_at DESC);
CREATE INDEX IF NOT EXISTS strategy_signals_evaluation_id_idx
  ON public.strategy_signals (evaluation_id);

COMMENT ON TABLE public.strategy_signals IS
  'Strategy Runtime signals (suggestion only). Never an order.';

-- Decision history view alias table for explicit decision audit trail
CREATE TABLE IF NOT EXISTS public.strategy_decision_history (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  evaluation_id       uuid NOT NULL REFERENCES public.strategy_evaluations (id) ON DELETE CASCADE,
  decision            text NOT NULL CHECK (
    decision IN ('no_action', 'watch', 'ready', 'blocked')
  ),
  reasons             jsonb NOT NULL DEFAULT '[]'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS strategy_decision_history_user_id_idx
  ON public.strategy_decision_history (user_id);
CREATE INDEX IF NOT EXISTS strategy_decision_history_recorded_at_idx
  ON public.strategy_decision_history (recorded_at DESC);

COMMENT ON TABLE public.strategy_decision_history IS
  'Immutable Strategy Runtime decision history. No execution.';
