-- =============================================================================
-- QuantForg Phase 1E: Durable MT5 worker control-plane state
-- Version: 20261109160000
--
-- Process-memory control plane alone does not survive Railway restarts.
-- This table stores host-slot worker assignment/lifecycle/heartbeat metadata.
--
-- IMPORTANT:
--   - Does NOT enable MULTI_ACCOUNT LIVE submit.
--   - Passwords/credentials are NEVER stored here.
--   - Lab synthetic user/account UUIDs are allowed without FK (nullable refs).
--   - DO NOT apply to Production without explicit owner approval + backup.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.mt5_worker_control_plane (
  worker_id              uuid PRIMARY KEY,
  host_code              text NOT NULL,
  slot_id                text NOT NULL,
  host_id                uuid,
  user_id                uuid,
  broker_account_id      uuid,
  lifecycle_status       text NOT NULL DEFAULT 'pending',
  runtime_session_id     text NOT NULL DEFAULT '',
  platform               text NOT NULL DEFAULT 'windows-local',
  last_heartbeat_at      timestamptz,
  last_health_check_at   timestamptz,
  last_error             text NOT NULL DEFAULT '',
  attempt_count          integer NOT NULL DEFAULT 0
                           CHECK (attempt_count >= 0),
  trade_allowed          boolean,
  account_login_verified text NOT NULL DEFAULT '',
  server_verified        text NOT NULL DEFAULT '',
  revoked                boolean NOT NULL DEFAULT false,
  metadata               jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at             timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at             timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_worker_cp_host_slot_nonempty
    CHECK (length(trim(host_code)) > 0 AND length(trim(slot_id)) > 0),
  CONSTRAINT mt5_worker_cp_lifecycle_check
    CHECK (lifecycle_status IN (
      'pending', 'provisioning', 'starting', 'authenticating', 'verifying',
      'ready', 'disconnected', 'error', 'reconnecting',
      'stopping', 'stopped', 'revoked'
    ))
);

-- One active (non-terminal) worker per host slot.
CREATE UNIQUE INDEX IF NOT EXISTS mt5_worker_cp_active_host_slot_uidx
  ON public.mt5_worker_control_plane (lower(host_code), lower(slot_id))
  WHERE revoked = false
    AND lifecycle_status NOT IN ('stopped', 'revoked');

-- One active worker per real user when user_id is present.
CREATE UNIQUE INDEX IF NOT EXISTS mt5_worker_cp_active_user_uidx
  ON public.mt5_worker_control_plane (user_id)
  WHERE user_id IS NOT NULL
    AND revoked = false
    AND lifecycle_status NOT IN ('stopped', 'revoked');

-- One active worker per real broker account when present.
CREATE UNIQUE INDEX IF NOT EXISTS mt5_worker_cp_active_account_uidx
  ON public.mt5_worker_control_plane (broker_account_id)
  WHERE broker_account_id IS NOT NULL
    AND revoked = false
    AND lifecycle_status NOT IN ('stopped', 'revoked');

CREATE INDEX IF NOT EXISTS mt5_worker_cp_heartbeat_idx
  ON public.mt5_worker_control_plane (last_heartbeat_at);

DROP TRIGGER IF EXISTS mt5_worker_cp_set_updated_at ON public.mt5_worker_control_plane;
CREATE TRIGGER mt5_worker_cp_set_updated_at
  BEFORE UPDATE ON public.mt5_worker_control_plane
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.mt5_worker_control_plane IS
  'Durable Windows MT5 worker control-plane state. Not LIVE order routing. No passwords.';

ALTER TABLE public.mt5_worker_control_plane ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mt5_worker_control_plane FORCE ROW LEVEL SECURITY;

CREATE POLICY mt5_worker_cp_deny_authenticated
  ON public.mt5_worker_control_plane
  FOR ALL TO authenticated
  USING (false)
  WITH CHECK (false);

REVOKE ALL ON TABLE public.mt5_worker_control_plane FROM anon, authenticated;
GRANT ALL ON TABLE public.mt5_worker_control_plane TO service_role;
