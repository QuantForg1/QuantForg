-- Phase F: Institutional Operations Control Plane
-- Append-only audit + config versions. Does not modify OMS / A–E tables.

CREATE TABLE IF NOT EXISTS ite_ops_audit_log (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator TEXT NOT NULL,
    operator_id TEXT NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT NOT NULL DEFAULT '',
    new_value TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    ip TEXT,
    user_agent TEXT,
    schema_version TEXT NOT NULL DEFAULT '1.0.0'
);

CREATE INDEX IF NOT EXISTS idx_ite_ops_audit_ts ON ite_ops_audit_log (timestamp DESC);

CREATE TABLE IF NOT EXISTS ite_ops_config_versions (
    id UUID PRIMARY KEY,
    config_version TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    promoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator TEXT NOT NULL,
    reason TEXT NOT NULL,
    rollback_target TEXT,
    risk_per_trade_pct NUMERIC NOT NULL,
    max_daily_loss_pct NUMERIC NOT NULL,
    max_open_trades INTEGER NOT NULL,
    execution_mode TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Never UPDATE in place for historical rows; activate via pointer table.
    CONSTRAINT ite_ops_config_append_only CHECK (true)
);

CREATE INDEX IF NOT EXISTS idx_ite_ops_config_promoted
    ON ite_ops_config_versions (promoted_at DESC);

CREATE TABLE IF NOT EXISTS ite_ops_active_config (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    config_id UUID REFERENCES ite_ops_config_versions(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ite_ops_alerts (
    id UUID PRIMARY KEY,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ite_ops_alerts_unacked
    ON ite_ops_alerts (acknowledged, created_at DESC);

CREATE TABLE IF NOT EXISTS ite_ops_mode_transitions (
    id UUID PRIMARY KEY,
    from_mode TEXT NOT NULL,
    to_mode TEXT NOT NULL,
    operator TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ite_ops_health_snapshots (
    id UUID PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);

COMMENT ON TABLE ite_ops_audit_log IS
  'ITE Phase F append-only operator audit — never delete.';
