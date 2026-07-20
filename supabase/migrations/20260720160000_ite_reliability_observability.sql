-- Phase G: Production Reliability & Observability
-- Does not modify OMS / trading tables.

CREATE TABLE IF NOT EXISTS ite_reliability_heartbeats (
    component TEXT PRIMARY KEY,
    at TIMESTAMPTZ NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ite_reliability_health_snapshots (
    id UUID PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    health_score INTEGER NOT NULL,
    degraded BOOLEAN NOT NULL DEFAULT FALSE,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ite_rel_health_checked
    ON ite_reliability_health_snapshots (checked_at DESC);

CREATE TABLE IF NOT EXISTS ite_reliability_traces (
    trace_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_id TEXT,
    symbol TEXT NOT NULL DEFAULT 'XAUUSD',
    spans JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ite_rel_traces_created
    ON ite_reliability_traces (created_at DESC);

CREATE TABLE IF NOT EXISTS ite_reliability_incidents (
    id UUID PRIMARY KEY,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL,
    escalation_level INTEGER NOT NULL DEFAULT 0,
    resolved_at TIMESTAMPTZ,
    acknowledged_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_ite_rel_incidents_open
    ON ite_reliability_incidents (status, created_at DESC);

CREATE TABLE IF NOT EXISTS ite_reliability_recovery_events (
    id UUID PRIMARY KEY,
    action TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    detail TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ite_rel_recovery_no_order_send CHECK (action <> 'order_send_retry')
);

CREATE TABLE IF NOT EXISTS ite_reliability_timeline (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    trace_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_ite_rel_timeline_ts
    ON ite_reliability_timeline (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ite_rel_timeline_cat
    ON ite_reliability_timeline (category, timestamp DESC);

CREATE TABLE IF NOT EXISTS ite_reliability_metrics_snapshots (
    id UUID PRIMARY KEY,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

COMMENT ON TABLE ite_reliability_recovery_events IS
  'Phase G recovery — never includes automatic order_send retry.';
