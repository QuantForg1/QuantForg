DROP TABLE IF EXISTS public.dispatch_delivery_events;

DROP INDEX IF EXISTS public.account_execution_intents_lease_idx;
DROP INDEX IF EXISTS public.account_execution_intents_claim_idx;

ALTER TABLE public.account_execution_intents
  DROP COLUMN IF EXISTS kill_switch,
  DROP COLUMN IF EXISTS next_retry_at,
  DROP COLUMN IF EXISTS max_attempts,
  DROP COLUMN IF EXISTS acked_at,
  DROP COLUMN IF EXISTS delivered_at,
  DROP COLUMN IF EXISTS delivery_status,
  DROP COLUMN IF EXISTS available_at,
  DROP COLUMN IF EXISTS lease_expires_at,
  DROP COLUMN IF EXISTS lease_owner_worker_id;
