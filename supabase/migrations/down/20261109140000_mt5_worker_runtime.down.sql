-- Down: 20261109140000_mt5_worker_runtime

DROP POLICY IF EXISTS worker_hosts_deny_authenticated ON public.worker_hosts;
DROP TRIGGER IF EXISTS worker_hosts_set_updated_at ON public.worker_hosts;
DROP TABLE IF EXISTS public.worker_hosts CASCADE;

DROP INDEX IF EXISTS public.execution_workers_heartbeat_idx;
DROP INDEX IF EXISTS public.execution_workers_host_id_idx;
DROP INDEX IF EXISTS public.execution_workers_lifecycle_idx;

ALTER TABLE public.execution_workers
  DROP CONSTRAINT IF EXISTS execution_workers_attempt_count_check;

ALTER TABLE public.execution_workers
  DROP CONSTRAINT IF EXISTS execution_workers_lifecycle_status_check;

ALTER TABLE public.execution_workers
  DROP COLUMN IF EXISTS server_verified,
  DROP COLUMN IF EXISTS account_login_verified,
  DROP COLUMN IF EXISTS trade_allowed,
  DROP COLUMN IF EXISTS attempt_count,
  DROP COLUMN IF EXISTS last_health_check_at,
  DROP COLUMN IF EXISTS lifecycle_status,
  DROP COLUMN IF EXISTS runtime_session_id,
  DROP COLUMN IF EXISTS host_id;
