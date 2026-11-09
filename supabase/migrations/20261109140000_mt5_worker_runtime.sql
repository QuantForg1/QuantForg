-- =============================================================================
-- QuantForg Phase 1B: MT5 worker runtime extensions
-- Version: 20261109140000
--
-- Extends execution_workers with lifecycle / host / heartbeat fields.
-- Rows remain ASSIGNMENT + CONTROL-PLANE metadata. They do NOT prove a live
-- MetaTrader terminal is running on a Windows host.
-- MULTI_ACCOUNT_* LIVE flags stay off. Do not apply to Production without
-- explicit owner approval.
-- =============================================================================

ALTER TABLE public.execution_workers
  ADD COLUMN IF NOT EXISTS host_id uuid,
  ADD COLUMN IF NOT EXISTS runtime_session_id text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS lifecycle_status text NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS last_health_check_at timestamptz,
  ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS trade_allowed boolean,
  ADD COLUMN IF NOT EXISTS account_login_verified text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS server_verified text NOT NULL DEFAULT '';

ALTER TABLE public.execution_workers
  DROP CONSTRAINT IF EXISTS execution_workers_lifecycle_status_check;

ALTER TABLE public.execution_workers
  ADD CONSTRAINT execution_workers_lifecycle_status_check
  CHECK (lifecycle_status IN (
    'pending', 'provisioning', 'starting', 'authenticating', 'verifying',
    'ready', 'disconnected', 'error', 'reconnecting',
    'stopping', 'stopped', 'revoked'
  ));

ALTER TABLE public.execution_workers
  DROP CONSTRAINT IF EXISTS execution_workers_attempt_count_check;

ALTER TABLE public.execution_workers
  ADD CONSTRAINT execution_workers_attempt_count_check
  CHECK (attempt_count >= 0);

CREATE INDEX IF NOT EXISTS execution_workers_lifecycle_idx
  ON public.execution_workers (lifecycle_status);

CREATE INDEX IF NOT EXISTS execution_workers_host_id_idx
  ON public.execution_workers (host_id)
  WHERE host_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS execution_workers_heartbeat_idx
  ON public.execution_workers (last_heartbeat_at);

COMMENT ON COLUMN public.execution_workers.lifecycle_status IS
  'Control-plane lifecycle. ready only after isolated MT5 auth+verify. Not LIVE-wired.';
COMMENT ON COLUMN public.execution_workers.host_id IS
  'Windows worker host identifier. Null until a host is assigned.';
COMMENT ON COLUMN public.execution_workers.runtime_session_id IS
  'Opaque agent session id — never a password or credential.';

-- ---------------------------------------------------------------------------
-- worker_hosts — capacity ledger for Windows hosts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.worker_hosts (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  host_code            text NOT NULL,
  region               text NOT NULL DEFAULT '',
  max_terminals        integer NOT NULL CHECK (max_terminals >= 1),
  allocated_terminals  integer NOT NULL DEFAULT 0 CHECK (allocated_terminals >= 0),
  cpu_percent          numeric(8, 2) NOT NULL DEFAULT 0,
  ram_percent          numeric(8, 2) NOT NULL DEFAULT 0,
  disk_percent         numeric(8, 2) NOT NULL DEFAULT 0,
  healthy              boolean NOT NULL DEFAULT true,
  notes                text NOT NULL DEFAULT '',
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT worker_hosts_code_nonempty CHECK (length(trim(host_code)) > 0),
  CONSTRAINT worker_hosts_allocated_le_max CHECK (allocated_terminals <= max_terminals)
);

CREATE UNIQUE INDEX IF NOT EXISTS worker_hosts_code_uidx
  ON public.worker_hosts (lower(host_code));

DROP TRIGGER IF EXISTS worker_hosts_set_updated_at ON public.worker_hosts;
CREATE TRIGGER worker_hosts_set_updated_at
  BEFORE UPDATE ON public.worker_hosts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.worker_hosts IS
  'Windows MT5 worker host capacity ledger. Empty until operators register hosts. Not auto-provisioned.';

ALTER TABLE public.worker_hosts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_hosts FORCE ROW LEVEL SECURITY;

CREATE POLICY worker_hosts_deny_authenticated
  ON public.worker_hosts
  FOR ALL TO authenticated
  USING (false)
  WITH CHECK (false);

REVOKE ALL ON TABLE public.worker_hosts FROM anon, authenticated;
GRANT ALL ON TABLE public.worker_hosts TO service_role;
