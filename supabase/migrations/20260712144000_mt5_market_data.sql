-- =============================================================================
-- QuantForg migration: MT5 Adapter Sprint 2 (symbol metadata cache)
-- Version: 20260712144000
-- Reversible: see supabase/migrations/down/20260712144000_mt5_market_data.down.sql
-- Depends on: 20260712143000_mt5_adapter
-- NOTE: Optional metadata/cache only — does NOT persist ticks.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.mt5_symbol_cache (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol            text NOT NULL,
  description       text NOT NULL DEFAULT '',
  digits            integer NOT NULL DEFAULT 5 CHECK (digits >= 0),
  point             text NOT NULL DEFAULT '0.00001',
  contract_size     text NOT NULL DEFAULT '100000',
  selected          boolean NOT NULL DEFAULT false,
  trade_mode        text NOT NULL DEFAULT '',
  currency_base     text NOT NULL DEFAULT '',
  currency_profit   text NOT NULL DEFAULT '',
  last_bid          text,
  last_ask          text,
  updated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_symbol_cache_symbol_nonempty CHECK (length(trim(symbol)) > 0),
  CONSTRAINT mt5_symbol_cache_user_symbol_uidx UNIQUE (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS mt5_symbol_cache_user_id_idx
  ON public.mt5_symbol_cache (user_id);
CREATE INDEX IF NOT EXISTS mt5_symbol_cache_selected_idx
  ON public.mt5_symbol_cache (user_id, selected);

CREATE TRIGGER mt5_symbol_cache_set_updated_at
  BEFORE UPDATE ON public.mt5_symbol_cache
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.mt5_symbol_cache IS
  'Optional MT5 symbol metadata cache. Ticks/candles are NOT stored here.';
