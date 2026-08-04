-- Signal Intelligence v2 — observed LIVE scan signals (read-only).
-- Never writes trades. Never mutates Trading Core / OMS / Gateway / MT5.

CREATE TABLE IF NOT EXISTS public.signal_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_as_of TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'NONE',
    badge TEXT,
    quality INTEGER,
    confidence INTEGER,
    probability NUMERIC,
    momentum INTEGER,
    structure INTEGER,
    strategy_id TEXT,
    session TEXT,
    reject BOOLEAN NOT NULL DEFAULT FALSE,
    blocking_gate TEXT,
    rr NUMERIC,
    expected_hold TEXT,
    factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_score JSONB NOT NULL DEFAULT '{}'::jsonb,
    source TEXT NOT NULL DEFAULT 'live_multi_asset_scan',
    UNIQUE (scan_as_of, symbol)
);

CREATE INDEX IF NOT EXISTS signal_history_symbol_observed_idx
    ON public.signal_history (symbol, observed_at DESC);

CREATE INDEX IF NOT EXISTS signal_history_observed_idx
    ON public.signal_history (observed_at DESC);

COMMENT ON TABLE public.signal_history IS
  'Signal Intelligence v2 — observed LIVE multi-asset scan rows (observation only).';

ALTER TABLE public.signal_history ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.signal_history FROM anon, authenticated;
GRANT ALL ON TABLE public.signal_history TO service_role;
