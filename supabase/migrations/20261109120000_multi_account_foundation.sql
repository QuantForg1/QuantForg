-- =============================================================================
-- QuantForg: Multi-user MT5 registry foundation (Phase 1a)
-- Version: 20261109120000
-- Reversible: see down/20261109120000_multi_account_foundation.down.sql
--
-- Product rule for this phase:
--   One QuantForg user  =  at most ONE non-revoked MT5 broker account
--   One active account  =  at most ONE active worker *assignment* row
--   Many users may each own one account (registry only)
--
-- Simultaneous MT5 LIVE execution is NOT supported by this migration.
-- execution_workers rows are assignment metadata only — not running terminals.
-- MULTI_ACCOUNT_* feature flags remain false until worker fleet is proven.
-- Existing Weltrade LIVE singleton path is unchanged.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extend broker_accounts: ownership verification + uniqueness
-- ---------------------------------------------------------------------------
ALTER TABLE public.broker_accounts
  ADD COLUMN IF NOT EXISTS ownership_verified boolean NOT NULL DEFAULT false;

ALTER TABLE public.broker_accounts
  ADD COLUMN IF NOT EXISTS ownership_verified_at timestamptz;

COMMENT ON COLUMN public.broker_accounts.ownership_verified IS
  'True only after successful isolated broker authentication. UI must not show Connected until verified.';
COMMENT ON COLUMN public.broker_accounts.ownership_verified_at IS
  'UTC timestamp of successful ownership verification.';

-- Global claim: same broker + server + login cannot be owned by two users.
CREATE UNIQUE INDEX IF NOT EXISTS broker_accounts_global_active_claim_uidx
  ON public.broker_accounts (
    broker_id,
    lower(trim(server)),
    lower(trim(external_account_id))
  )
  WHERE status <> 'revoked';

-- One non-revoked MT5 account per QuantForg user.
CREATE UNIQUE INDEX IF NOT EXISTS broker_accounts_one_active_per_user_uidx
  ON public.broker_accounts (user_id)
  WHERE status <> 'revoked';

-- ---------------------------------------------------------------------------
-- platform_risk_policy — Admin global ranges / defaults (single active row)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.platform_risk_policy (
  id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  is_active                       boolean NOT NULL DEFAULT true,
  max_planned_risk_pct            numeric(8, 4) NOT NULL DEFAULT 20.0
                                    CHECK (max_planned_risk_pct > 0 AND max_planned_risk_pct <= 20),
  max_aggregate_open_risk_pct     numeric(8, 4) NOT NULL DEFAULT 30.0
                                    CHECK (max_aggregate_open_risk_pct > 0 AND max_aggregate_open_risk_pct <= 30),
  max_lot                         numeric(12, 4) NOT NULL DEFAULT 0.01
                                    CHECK (max_lot > 0 AND max_lot <= 0.01),
  max_daily_loss_pct              numeric(8, 4) NOT NULL DEFAULT 48.0
                                    CHECK (max_daily_loss_pct > 0 AND max_daily_loss_pct <= 48),
  max_concurrent_positions        integer NOT NULL DEFAULT 1
                                    CHECK (max_concurrent_positions BETWEEN 1 AND 1),
  default_planned_risk_pct        numeric(8, 4) NOT NULL DEFAULT 20.0
                                    CHECK (default_planned_risk_pct > 0 AND default_planned_risk_pct <= 20),
  default_aggregate_open_risk_pct numeric(8, 4) NOT NULL DEFAULT 30.0
                                    CHECK (default_aggregate_open_risk_pct > 0 AND default_aggregate_open_risk_pct <= 30),
  default_max_lot                 numeric(12, 4) NOT NULL DEFAULT 0.01
                                    CHECK (default_max_lot > 0 AND default_max_lot <= 0.01),
  default_daily_loss_pct          numeric(8, 4) NOT NULL DEFAULT 48.0
                                    CHECK (default_daily_loss_pct > 0 AND default_daily_loss_pct <= 48),
  default_max_concurrent_positions integer NOT NULL DEFAULT 1
                                    CHECK (default_max_concurrent_positions BETWEEN 1 AND 1),
  stop_atr_multiplier             numeric(8, 4) NOT NULL DEFAULT 1.00,
  xauusd_commission               numeric(12, 4) NOT NULL DEFAULT 0,
  max_spread                      numeric(12, 4) NOT NULL DEFAULT 1.00,
  min_trade_quality               integer NOT NULL DEFAULT 70
                                    CHECK (min_trade_quality BETWEEN 70 AND 100),
  min_reward_risk                 numeric(8, 4) NOT NULL DEFAULT 0.20
                                    CHECK (min_reward_risk >= 0.20),
  global_emergency_stop           boolean NOT NULL DEFAULT false,
  multi_account_live_enabled      boolean NOT NULL DEFAULT false,
  notes                           text NOT NULL DEFAULT '',
  updated_by                      uuid REFERENCES public.users (id) ON DELETE SET NULL,
  created_at                      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at                      timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_risk_policy_one_active_uidx
  ON public.platform_risk_policy (is_active)
  WHERE is_active;

DROP TRIGGER IF EXISTS platform_risk_policy_set_updated_at ON public.platform_risk_policy;
CREATE TRIGGER platform_risk_policy_set_updated_at
  BEFORE UPDATE ON public.platform_risk_policy
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.platform_risk_policy IS
  'Admin global risk ranges/defaults for multi-user registry. LIVE fan-out stays off.';

INSERT INTO public.platform_risk_policy (is_active, notes)
SELECT true, 'Phase 1a seed — mirrors owner hard ceilings; one account per user'
WHERE NOT EXISTS (
  SELECT 1 FROM public.platform_risk_policy WHERE is_active
);

-- ---------------------------------------------------------------------------
-- user_risk_settings — one active profile per user (independent copies)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_risk_settings (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_account_id        uuid REFERENCES public.broker_accounts (id) ON DELETE SET NULL,
  planned_risk_pct         numeric(8, 4) NOT NULL
                             CHECK (planned_risk_pct > 0 AND planned_risk_pct <= 20),
  aggregate_open_risk_pct  numeric(8, 4) NOT NULL
                             CHECK (aggregate_open_risk_pct > 0 AND aggregate_open_risk_pct <= 30),
  max_lot                  numeric(12, 4) NOT NULL
                             CHECK (max_lot > 0 AND max_lot <= 0.01),
  daily_loss_pct           numeric(8, 4) NOT NULL
                             CHECK (daily_loss_pct > 0 AND daily_loss_pct <= 48),
  max_concurrent_positions integer NOT NULL
                             CHECK (max_concurrent_positions BETWEEN 1 AND 1),
  is_active                boolean NOT NULL DEFAULT true,
  source                   text NOT NULL DEFAULT 'default_copy'
                             CHECK (source IN ('default_copy', 'user_edit', 'admin_apply')),
  created_at               timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at               timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT user_risk_settings_aggregate_ge_planned
    CHECK (aggregate_open_risk_pct >= planned_risk_pct)
);

CREATE UNIQUE INDEX IF NOT EXISTS user_risk_settings_one_active_per_user_uidx
  ON public.user_risk_settings (user_id)
  WHERE is_active;

CREATE INDEX IF NOT EXISTS user_risk_settings_user_id_idx
  ON public.user_risk_settings (user_id);

DROP TRIGGER IF EXISTS user_risk_settings_set_updated_at ON public.user_risk_settings;
CREATE TRIGGER user_risk_settings_set_updated_at
  BEFORE UPDATE ON public.user_risk_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.user_risk_settings IS
  'Per-user editable risk knobs (one active row). Effective = strictest of user/admin/hard ceiling.';

-- ---------------------------------------------------------------------------
-- execution_workers — assignment registry ONLY (not running terminals)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.execution_workers (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_code          text NOT NULL,
  user_id              uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_account_id    uuid NOT NULL
                         REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  platform_code        text NOT NULL DEFAULT 'mt5'
                         CHECK (platform_code IN ('mt5', 'mt4', 'ctrader', 'dxtrade', 'other')),
  status               text NOT NULL DEFAULT 'registered'
                         CHECK (status IN (
                           'registered', 'healthy', 'degraded', 'offline', 'disabled'
                         )),
  gateway_base_url     text NOT NULL DEFAULT '',
  last_heartbeat_at    timestamptz,
  last_error           text NOT NULL DEFAULT '',
  metadata             jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT execution_workers_code_nonempty
    CHECK (length(trim(worker_code)) > 0),
  CONSTRAINT execution_workers_active_requires_account
    CHECK (
      status = 'disabled'
      OR (broker_account_id IS NOT NULL AND user_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS execution_workers_code_uidx
  ON public.execution_workers (lower(worker_code));

-- At most one active worker assignment per broker account.
CREATE UNIQUE INDEX IF NOT EXISTS execution_workers_one_active_per_account_uidx
  ON public.execution_workers (broker_account_id)
  WHERE status IN ('registered', 'healthy', 'degraded', 'offline');

-- At most one active worker assignment per user (matches one-account-per-user).
CREATE UNIQUE INDEX IF NOT EXISTS execution_workers_one_active_per_user_uidx
  ON public.execution_workers (user_id)
  WHERE status IN ('registered', 'healthy', 'degraded', 'offline');

CREATE INDEX IF NOT EXISTS execution_workers_account_idx
  ON public.execution_workers (broker_account_id);

CREATE INDEX IF NOT EXISTS execution_workers_user_idx
  ON public.execution_workers (user_id);

DROP TRIGGER IF EXISTS execution_workers_set_updated_at ON public.execution_workers;
CREATE TRIGGER execution_workers_set_updated_at
  BEFORE UPDATE ON public.execution_workers
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.execution_workers IS
  'Worker ASSIGNMENT registry only. Rows do not mean a live MT5 terminal is running. Simultaneous MT5 LIVE execution is NOT supported yet.';

-- ---------------------------------------------------------------------------
-- central_signals — durable qualified signal catalog
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.central_signals (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key    text NOT NULL,
  symbol             text NOT NULL,
  side               text NOT NULL CHECK (side IN ('BUY', 'SELL')),
  quality            integer NOT NULL CHECK (quality BETWEEN 0 AND 100),
  entry_price        numeric(20, 8),
  stop_loss          numeric(20, 8),
  take_profit        numeric(20, 8),
  strategy_id        text NOT NULL DEFAULT '',
  trace_id           text NOT NULL DEFAULT '',
  status             text NOT NULL DEFAULT 'recorded'
                       CHECK (status IN ('recorded', 'dispatching', 'dispatched', 'expired')),
  payload            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT central_signals_idempotency_nonempty
    CHECK (length(trim(idempotency_key)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS central_signals_idempotency_uidx
  ON public.central_signals (idempotency_key);

CREATE INDEX IF NOT EXISTS central_signals_created_at_idx
  ON public.central_signals (created_at DESC);

DROP TRIGGER IF EXISTS central_signals_set_updated_at ON public.central_signals;
CREATE TRIGGER central_signals_set_updated_at
  BEFORE UPDATE ON public.central_signals
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.central_signals IS
  'Durable central signal intents. Dispatch to workers is feature-flagged and OFF by default.';

-- ---------------------------------------------------------------------------
-- account_execution_intents — per-user (one account) execution state
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.account_execution_intents (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id            uuid NOT NULL REFERENCES public.central_signals (id) ON DELETE CASCADE,
  user_id              uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_account_id    uuid NOT NULL REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  worker_id            uuid REFERENCES public.execution_workers (id) ON DELETE SET NULL,
  idempotency_key      text NOT NULL,
  state                text NOT NULL DEFAULT 'received'
                         CHECK (state IN (
                           'received', 'eligibility_pending', 'eligible', 'blocked',
                           'risk_validated', 'queued', 'submitting', 'acknowledged',
                           'partial_fill', 'filled', 'rejected', 'cancelled',
                           'dead_letter', 'unknown'
                         )),
  block_reason         text NOT NULL DEFAULT '',
  planned_volume       numeric(20, 8),
  broker_ticket        text NOT NULL DEFAULT '',
  attempt_count        integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error           text NOT NULL DEFAULT '',
  payload              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT account_execution_intents_idempotency_nonempty
    CHECK (length(trim(idempotency_key)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS account_execution_intents_idempotency_uidx
  ON public.account_execution_intents (idempotency_key);

CREATE UNIQUE INDEX IF NOT EXISTS account_execution_intents_signal_account_uidx
  ON public.account_execution_intents (signal_id, broker_account_id);

CREATE UNIQUE INDEX IF NOT EXISTS account_execution_intents_signal_user_uidx
  ON public.account_execution_intents (signal_id, user_id);

CREATE INDEX IF NOT EXISTS account_execution_intents_user_id_idx
  ON public.account_execution_intents (user_id);

CREATE INDEX IF NOT EXISTS account_execution_intents_state_idx
  ON public.account_execution_intents (state);

DROP TRIGGER IF EXISTS account_execution_intents_set_updated_at
  ON public.account_execution_intents;
CREATE TRIGGER account_execution_intents_set_updated_at
  BEFORE UPDATE ON public.account_execution_intents
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.account_execution_intents IS
  'Per-user execution state for one central signal. One user failure must not block others. Not LIVE-wired yet.';
