-- =============================================================================
-- QuantForg migration: Walk-Forward Validation Engine
-- Version: 20260712153000
-- Reversible: see supabase/migrations/down/20260712153000_walkforward.down.sql
-- Depends on: users
-- NOTE: Offline validation only — no credentials, no execution, no order_send.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.walkforward_runs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  request_id          text NOT NULL,
  symbol              text NOT NULL,
  timeframe           text NOT NULL DEFAULT 'm15',
  status              text NOT NULL CHECK (
    status IN ('pending', 'running', 'completed', 'failed')
  ),
  promotion           text CHECK (
    promotion IS NULL OR promotion IN ('promote_to_paper', 'needs_rework', 'reject')
  ),
  window_config       jsonb NOT NULL DEFAULT '{}'::jsonb,
  folds               jsonb NOT NULL DEFAULT '[]'::jsonb,
  aggregated_is       jsonb NOT NULL DEFAULT '{}'::jsonb,
  aggregated_oos      jsonb NOT NULL DEFAULT '{}'::jsonb,
  robustness          jsonb NOT NULL DEFAULT '{}'::jsonb,
  combined_equity     jsonb NOT NULL DEFAULT '[]'::jsonb,
  report              jsonb NOT NULL DEFAULT '{}'::jsonb,
  bar_count           integer NOT NULL DEFAULT 0,
  fold_count          integer NOT NULL DEFAULT 0,
  error_message       text NOT NULL DEFAULT '',
  started_at          timestamptz,
  finished_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT walkforward_runs_request_id_nonempty CHECK (length(trim(request_id)) > 0),
  CONSTRAINT walkforward_runs_symbol_nonempty CHECK (length(trim(symbol)) > 0)
);

CREATE INDEX IF NOT EXISTS walkforward_runs_user_id_idx
  ON public.walkforward_runs (user_id);
CREATE INDEX IF NOT EXISTS walkforward_runs_created_at_idx
  ON public.walkforward_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS walkforward_runs_status_idx
  ON public.walkforward_runs (status);
CREATE INDEX IF NOT EXISTS walkforward_runs_user_request_idx
  ON public.walkforward_runs (user_id, request_id);

COMMENT ON TABLE public.walkforward_runs IS
  'Walk-Forward validation runs (IS/OOS). Never live trading.';

CREATE TABLE IF NOT EXISTS public.walkforward_oos_metrics (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  walkforward_id      uuid NOT NULL REFERENCES public.walkforward_runs (id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS walkforward_oos_metrics_user_id_idx
  ON public.walkforward_oos_metrics (user_id);
CREATE INDEX IF NOT EXISTS walkforward_oos_metrics_run_idx
  ON public.walkforward_oos_metrics (walkforward_id);

COMMENT ON TABLE public.walkforward_oos_metrics IS
  'Aggregated out-of-sample metrics for walk-forward runs.';

CREATE TABLE IF NOT EXISTS public.walkforward_robustness_reports (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  walkforward_id      uuid NOT NULL UNIQUE REFERENCES public.walkforward_runs (id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
  recorded_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS walkforward_robustness_user_id_idx
  ON public.walkforward_robustness_reports (user_id);

COMMENT ON TABLE public.walkforward_robustness_reports IS
  'Robustness / overfitting reports for walk-forward runs.';
