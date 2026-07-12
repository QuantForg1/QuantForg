-- =============================================================================
-- QuantForg migration: MT5 Adapter Sprint 3 (order validation history)
-- Version: 20260712145000
-- Reversible: see supabase/migrations/down/20260712145000_mt5_order_validation.down.sql
-- Depends on: 20260712143000_mt5_adapter
-- NOTE: Validation history only — never stores credentials or live orders.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.mt5_order_validations (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL DEFAULT 'market',
  volume              text NOT NULL,
  valid               boolean NOT NULL DEFAULT false,
  retcode             integer NOT NULL DEFAULT 0,
  expected_margin     text NOT NULL DEFAULT '0',
  estimated_profit    text NOT NULL DEFAULT '0',
  messages            jsonb NOT NULL DEFAULT '[]'::jsonb,
  checks              jsonb NOT NULL DEFAULT '{}'::jsonb,
  request_snapshot    jsonb NOT NULL DEFAULT '{}'::jsonb,
  validated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_order_validations_symbol_nonempty CHECK (length(trim(symbol)) > 0),
  CONSTRAINT mt5_order_validations_volume_nonempty CHECK (length(trim(volume)) > 0)
);

CREATE INDEX IF NOT EXISTS mt5_order_validations_user_id_idx
  ON public.mt5_order_validations (user_id);
CREATE INDEX IF NOT EXISTS mt5_order_validations_validated_at_idx
  ON public.mt5_order_validations (validated_at DESC);
CREATE INDEX IF NOT EXISTS mt5_order_validations_symbol_idx
  ON public.mt5_order_validations (symbol);

COMMENT ON TABLE public.mt5_order_validations IS
  'MT5 order validation history (Sprint 3). No credentials. No order_send.';
