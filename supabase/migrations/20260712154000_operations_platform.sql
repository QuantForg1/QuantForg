-- =============================================================================
-- QuantForg migration: Operations & Observability Platform
-- Version: 20260712154000
-- Reversible: see supabase/migrations/down/20260712154000_operations_platform.down.sql
-- NOTE: Operational only — no credentials, no execution, no order_send, no AI.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.system_alerts (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                text NOT NULL,
  name                text NOT NULL,
  severity            text NOT NULL CHECK (
    severity IN ('info', 'warning', 'critical')
  ),
  status              text NOT NULL CHECK (
    status IN ('open', 'acknowledged', 'resolved')
  ),
  component           text NOT NULL CHECK (
    component IN (
      'system', 'broker', 'mt5', 'api', 'database', 'queue', 'background_jobs'
    )
  ),
  message             text NOT NULL DEFAULT '',
  details             jsonb NOT NULL DEFAULT '{}'::jsonb,
  triggered_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  resolved_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT system_alerts_code_nonempty CHECK (length(trim(code)) > 0),
  CONSTRAINT system_alerts_name_nonempty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS system_alerts_code_idx
  ON public.system_alerts (code);
CREATE INDEX IF NOT EXISTS system_alerts_status_idx
  ON public.system_alerts (status);
CREATE INDEX IF NOT EXISTS system_alerts_triggered_at_idx
  ON public.system_alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS system_alerts_open_code_idx
  ON public.system_alerts (code)
  WHERE status IN ('open', 'acknowledged');

COMMENT ON TABLE public.system_alerts IS
  'Operational alerts (info/warning/critical). Never trading/execution.';

CREATE TABLE IF NOT EXISTS public.system_metrics (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS system_metrics_recorded_at_idx
  ON public.system_metrics (recorded_at DESC);

COMMENT ON TABLE public.system_metrics IS
  'Persisted operational metrics snapshots (latency, errors, throughput, cache, jobs).';

CREATE TABLE IF NOT EXISTS public.health_history (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  overall             text NOT NULL CHECK (
    overall IN ('healthy', 'degraded', 'unhealthy', 'unknown')
  ),
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS health_history_recorded_at_idx
  ON public.health_history (recorded_at DESC);
CREATE INDEX IF NOT EXISTS health_history_overall_idx
  ON public.health_history (overall);

COMMENT ON TABLE public.health_history IS
  'Point-in-time health dashboard history for operators.';
