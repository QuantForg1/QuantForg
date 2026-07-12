-- Down: 20260712141000_broker_sessions

DROP TRIGGER IF EXISTS broker_sessions_set_updated_at ON public.broker_sessions;
DROP TABLE IF EXISTS public.broker_sessions CASCADE;

DROP INDEX IF EXISTS broker_credentials_status_idx;
ALTER TABLE public.broker_credentials DROP COLUMN IF EXISTS status;
