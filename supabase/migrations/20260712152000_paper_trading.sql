-- =============================================================================
-- QuantForg migration: Paper Trading Engine
-- Version: 20260712152000
-- Reversible: see supabase/migrations/down/20260712152000_paper_trading.down.sql
-- Depends on: users
-- NOTE: Paper trading only — live quotes, simulated fills. No order_send.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.paper_portfolios (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL UNIQUE REFERENCES public.users (id) ON DELETE CASCADE,
  initial_balance     text NOT NULL,
  balance             text NOT NULL,
  equity              text NOT NULL,
  floating_pnl        text NOT NULL DEFAULT '0',
  realized_pnl        text NOT NULL DEFAULT '0',
  margin              text NOT NULL DEFAULT '0',
  peak_equity         text NOT NULL,
  max_drawdown_pct    text NOT NULL DEFAULT '0',
  snapshot            jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS paper_portfolios_user_id_idx
  ON public.paper_portfolios (user_id);

COMMENT ON TABLE public.paper_portfolios IS
  'Paper trading virtual portfolios. Never a live broker account.';

CREATE TABLE IF NOT EXISTS public.paper_orders (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL CHECK (order_type IN ('market', 'limit', 'stop')),
  volume              text NOT NULL,
  status              text NOT NULL CHECK (
    status IN ('pending', 'accepted', 'partially_filled', 'filled', 'rejected', 'cancelled')
  ),
  requested_price     text,
  fill_price          text,
  filled_volume       text NOT NULL DEFAULT '0',
  stop_loss           text,
  take_profit         text,
  spread              text NOT NULL DEFAULT '0',
  slippage            text NOT NULL DEFAULT '0',
  commission          text NOT NULL DEFAULT '0',
  rejection_reason    text NOT NULL DEFAULT '',
  position_id         uuid,
  client_order_id     text NOT NULL DEFAULT '',
  submitted_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  filled_at           timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT paper_orders_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS paper_orders_user_id_idx ON public.paper_orders (user_id);
CREATE INDEX IF NOT EXISTS paper_orders_status_idx ON public.paper_orders (status);
CREATE INDEX IF NOT EXISTS paper_orders_submitted_at_idx
  ON public.paper_orders (submitted_at DESC);

COMMENT ON TABLE public.paper_orders IS
  'Paper orders (market/limit/stop). Simulated fills only.';

CREATE TABLE IF NOT EXISTS public.paper_positions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  status              text NOT NULL CHECK (
    status IN ('opened', 'partially_closed', 'closed')
  ),
  volume              text NOT NULL,
  remaining_volume    text NOT NULL,
  entry_price         text NOT NULL,
  current_price       text NOT NULL,
  stop_loss           text,
  take_profit         text,
  floating_pnl        text NOT NULL DEFAULT '0',
  realized_pnl        text NOT NULL DEFAULT '0',
  commission          text NOT NULL DEFAULT '0',
  order_id            uuid,
  opened_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  closed_at           timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT paper_positions_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS paper_positions_user_id_idx
  ON public.paper_positions (user_id);
CREATE INDEX IF NOT EXISTS paper_positions_status_idx
  ON public.paper_positions (status);

COMMENT ON TABLE public.paper_positions IS
  'Paper positions lifecycle (opened/partially_closed/closed).';

CREATE TABLE IF NOT EXISTS public.paper_trades (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  volume              text NOT NULL,
  entry_price         text NOT NULL,
  exit_price          text NOT NULL,
  pnl                 text NOT NULL,
  commission          text NOT NULL DEFAULT '0',
  spread              text NOT NULL DEFAULT '0',
  slippage            text NOT NULL DEFAULT '0',
  position_id         uuid,
  order_id            uuid,
  opened_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  closed_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT paper_trades_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS paper_trades_user_id_idx ON public.paper_trades (user_id);
CREATE INDEX IF NOT EXISTS paper_trades_closed_at_idx
  ON public.paper_trades (closed_at DESC);

COMMENT ON TABLE public.paper_trades IS
  'Closed/partial paper trade history for performance.';

CREATE TABLE IF NOT EXISTS public.paper_performance (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL UNIQUE REFERENCES public.users (id) ON DELETE CASCADE,
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS paper_performance_user_id_idx
  ON public.paper_performance (user_id);

COMMENT ON TABLE public.paper_performance IS
  'Persisted paper trading performance snapshots.';
