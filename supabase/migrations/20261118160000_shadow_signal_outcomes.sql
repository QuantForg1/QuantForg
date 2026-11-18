-- HYPOTHETICAL outcomes of recorded signals (accepted and rejected).
-- One row per signal_history intent id: the primary key prevents duplicate
-- evaluation. Written by the backend (service role) only. Never combined with
-- LIVE or DEMO P/L and never read by the trading path.

CREATE TABLE IF NOT EXISTS public.shadow_signal_outcomes (
    signal_id UUID PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL DEFAULT 'XAUUSD',
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    accepted BOOLEAN NOT NULL,
    blocking_gate TEXT,
    gate_family TEXT NOT NULL,
    news_condition TEXT NOT NULL,
    strategy TEXT,
    session TEXT,
    hour_utc SMALLINT NOT NULL,
    quality INTEGER,
    confidence INTEGER,
    regime_proxy TEXT NOT NULL,
    factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    entry_price NUMERIC NOT NULL,
    spread NUMERIC NOT NULL,
    stop_distance NUMERIC,
    target_distance NUMERIC,
    slippage_per_side NUMERIC NOT NULL,
    commission_usd NUMERIC,
    crosses_rollover BOOLEAN NOT NULL DEFAULT FALSE,
    move_m1 NUMERIC,
    move_m5 NUMERIC,
    move_m15 NUMERIC,
    move_m30 NUMERIC,
    bracket TEXT,
    r_multiple NUMERIC,
    net_usd_min_lot NUMERIC,
    status TEXT NOT NULL CHECK (status IN ('complete', 'incomplete', 'ambiguous')),
    status_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    label TEXT NOT NULL DEFAULT 'HYPOTHETICAL' CHECK (label = 'HYPOTHETICAL')
);

CREATE INDEX IF NOT EXISTS shadow_signal_outcomes_observed_at_idx
    ON public.shadow_signal_outcomes (observed_at);

COMMENT ON TABLE public.shadow_signal_outcomes IS
  'HYPOTHETICAL replay of recorded signals (Shadow Signal Evaluator). Service role only. Not LIVE/DEMO P/L.';

ALTER TABLE public.shadow_signal_outcomes ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.shadow_signal_outcomes FROM anon, authenticated;
GRANT ALL ON TABLE public.shadow_signal_outcomes TO service_role;
