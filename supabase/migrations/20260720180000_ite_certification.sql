-- Phase H: Production Validation & Certification
-- Measurement only. Does not modify OMS / trading tables.

CREATE TABLE IF NOT EXISTS ite_certification_reports (
    id UUID PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    go_nogo TEXT NOT NULL,
    production_ready BOOLEAN NOT NULL DEFAULT FALSE,
    overall_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ite_cert_reports_generated
    ON ite_certification_reports (generated_at DESC);

CREATE TABLE IF NOT EXISTS ite_certification_certificates (
    id UUID PRIMARY KEY,
    report_id UUID REFERENCES ite_certification_reports (id),
    version TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    promotion_status TEXT NOT NULL,
    passed_tests JSONB NOT NULL DEFAULT '[]'::jsonb,
    known_limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    operator_approval TEXT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ite_cert_issued
    ON ite_certification_certificates (issued_at DESC);

CREATE TABLE IF NOT EXISTS ite_certification_canary_snapshots (
    id UUID PRIMARY KEY,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_trades INTEGER NOT NULL DEFAULT 0,
    win_rate_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0,
    expectancy DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    execution_success_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    oms_errors INTEGER NOT NULL DEFAULT 0,
    gateway_errors INTEGER NOT NULL DEFAULT 0,
    mt5_errors INTEGER NOT NULL DEFAULT 0,
    duplicate_prevented INTEGER NOT NULL DEFAULT 0,
    duplicate_executions INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ite_certification_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report_id UUID
);

COMMENT ON TABLE ite_certification_reports IS
  'Phase H certification — measurement only; never triggers order_send.';
