DROP POLICY IF EXISTS mt5_worker_cp_deny_authenticated ON public.mt5_worker_control_plane;
DROP TRIGGER IF EXISTS mt5_worker_cp_set_updated_at ON public.mt5_worker_control_plane;
DROP INDEX IF EXISTS public.mt5_worker_cp_heartbeat_idx;
DROP INDEX IF EXISTS public.mt5_worker_cp_active_account_uidx;
DROP INDEX IF EXISTS public.mt5_worker_cp_active_user_uidx;
DROP INDEX IF EXISTS public.mt5_worker_cp_active_host_slot_uidx;
DROP TABLE IF EXISTS public.mt5_worker_control_plane CASCADE;
