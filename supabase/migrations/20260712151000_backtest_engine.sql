-- =============================================================================
-- QuantForg migration: Backtesting Engine
-- Version: 20260712151000
-- Reversible: see supabase/migrations/down/20260712151000_backtest_engine.down.sql
-- Depends on: users
-- NOTE: Offline simulation only — no credentials, no execution, no order_send.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.backtest_runs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  symbol              text NOT NULL,
  timeframe           text NOT NULL DEFAULT 'm15',
  status              text NOT NULL CHECK (
    status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')
  ),
  replay_mode         text NOT NULL DEFAULT 'candle' CHECK (
    replay_mode IN ('candle', 'tick')
  ),
  initial_balance     text NOT NULL,
  assumptions         jsonb NOT NULL DEFAULT '{}'::jsonb,
  metrics             jsonb NOT NULL DEFAULT '{}'::jsonb,
  equity_curve        jsonb NOT NULL DEFAULT '[]'::jsonb,
  portfolio_snapshot  jsonb NOT NULL DEFAULT '{}'::jsonb,
  replay_state        jsonb NOT NULL DEFAULT '{}'::jsonb,
  trade_count         integer NOT NULL DEFAULT 0,
  bar_count           integer NOT NULL DEFAULT 0,
  error_message       text NOT NULL DEFAULT '',
  started_at          timestamptz,
  finished_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT backtest_runs_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT backtest_runs_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS backtest_runs_user_id_idx
  ON public.backtest_runs (user_id);
CREATE INDEX IF NOT EXISTS backtest_runs_created_at_idx
  ON public.backtest_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS backtest_runs_status_idx
  ON public.backtest_runs (status);
CREATE INDEX IF NOT EXISTS backtest_runs_user_request_idx
  ON public.backtest_runs (user_id, request_id);

COMMENT ON TABLE public.backtest_runs IS
  'Backtesting Engine runs (offline). Metrics + equity curves. No live trading.';

CREATE TABLE IF NOT EXISTS public.backtest_trades (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  backtest_id         uuid NOT NULL REFERENCES public.backtest_runs (id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  symbol              text NOT NULL,
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  status              text NOT NULL CHECK (status IN ('open', 'closed')),
  volume              text NOT NULL,
  entry_price         text NOT NULL,
  exit_price          text,
  stop_loss           text,
  take_profit         text,
  spread              text NOT NULL DEFAULT '0',
  slippage            text NOT NULL DEFAULT '0',
  fees                text NOT NULL DEFAULT '0',
  pnl                 text NOT NULL DEFAULT '0',
  exit_reason         text,
  opened_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  closed_at           timestamptz,
  bar_index_open      integer NOT NULL DEFAULT 0,
  bar_index_close     integer,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT backtest_trades_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS backtest_trades_backtest_id_idx
  ON public.backtest_trades (backtest_id);
CREATE INDEX IF NOT EXISTS backtest_trades_user_id_idx
  ON public.backtest_trades (user_id);

COMMENT ON TABLE public.backtest_trades IS
  'Simulated trades from backtests. Never sent to a broker.';

CREATE TABLE IF NOT EXISTS public.backtest_metrics (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  backtest_id         uuid NOT NULL UNIQUE REFERENCES public.backtest_runs (id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS backtest_metrics_user_id_idx
  ON public.backtest_metrics (user_id);

COMMENT ON TABLE public.backtest_metrics IS
  'Persisted backtest metrics snapshot. Offline only.';

CREATE TABLE IF NOT EXISTS public.backtest_equity_curves (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  backtest_id         uuid NOT NULL UNIQUE REFERENCES public.backtest_runs (id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  points              jsonb NOT NULL DEFAULT '[]'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS backtest_equity_curves_user_id_idx
  ON public.backtest_equity_curves (user_id);

COMMENT ON TABLE public.backtest_equity_curves IS
  'Equity / balance / drawdown curve points for a backtest run.';
