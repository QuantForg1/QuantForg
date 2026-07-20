-- Phase E: Institutional Research Platform — append-only results schema.
-- Does not modify OMS / Phase A–D tables.

CREATE TABLE IF NOT EXISTS ite_research_simulations (
    id UUID PRIMARY KEY,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    strategy_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    git_commit TEXT,
    bars_processed INTEGER NOT NULL DEFAULT 0,
    trade_count INTEGER NOT NULL DEFAULT 0,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Never UPDATE metrics rows in place; insert new runs only.
    CONSTRAINT ite_research_simulations_append_only CHECK (true)
);

CREATE INDEX IF NOT EXISTS idx_ite_research_simulations_stored_at
    ON ite_research_simulations (stored_at DESC);

CREATE INDEX IF NOT EXISTS idx_ite_research_simulations_strategy
    ON ite_research_simulations (strategy_version, config_version);

CREATE TABLE IF NOT EXISTS ite_research_trades (
    id UUID PRIMARY KEY,
    simulation_id UUID NOT NULL REFERENCES ite_research_simulations(id),
    trade_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ite_research_trades_sim
    ON ite_research_trades (simulation_id);

CREATE TABLE IF NOT EXISTS ite_research_walkforward (
    id UUID PRIMARY KEY,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mode TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    pass_ratio NUMERIC NOT NULL,
    report JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS ite_research_monte_carlo (
    id UUID PRIMARY KEY,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    simulation_id UUID REFERENCES ite_research_simulations(id),
    iterations INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    report JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS ite_research_promotions (
    id UUID PRIMARY KEY,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    simulation_id UUID REFERENCES ite_research_simulations(id),
    target TEXT NOT NULL DEFAULT 'canary',
    eligible BOOLEAN NOT NULL,
    report JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS ite_research_optimizations (
    id UUID PRIMARY KEY,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    top_sets JSONB NOT NULL,
    config_version TEXT NOT NULL
);

COMMENT ON TABLE ite_research_simulations IS
  'ITE Phase E append-only simulation results — never overwrite.';
