-- Live trade journal for operator alerts and daily/weekly summaries.
-- One row per MT5 position ticket; written by the backend (service role) only.
-- Survives Railway redeploys so open trades, SL/TP, P/L and R are never lost.

CREATE TABLE IF NOT EXISTS public.live_trade_journal (
    ticket BIGINT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    volume NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    stop_loss NUMERIC NOT NULL DEFAULT 0,
    take_profit NUMERIC NOT NULL DEFAULT 0,
    spread NUMERIC,
    planned_risk_usd NUMERIC,
    equity_at_open NUMERIC,
    opened_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    closed_at TIMESTAMPTZ,
    close_price NUMERIC,
    pnl NUMERIC,
    r_multiple NUMERIC,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS live_trade_journal_closed_at_idx
    ON public.live_trade_journal (closed_at);

COMMENT ON TABLE public.live_trade_journal IS
  'Live robot trades (MT5 tickets): entry, SL/TP, planned risk, P/L, R. Service role only.';

ALTER TABLE public.live_trade_journal ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.live_trade_journal FROM anon, authenticated;
GRANT ALL ON TABLE public.live_trade_journal TO service_role;
