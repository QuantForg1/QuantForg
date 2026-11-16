-- Robot Control Center: account-scoped robot state + audited control events.
-- Additive only. Backend (service_role) writes; owners read their own rows.

CREATE TABLE IF NOT EXISTS public.robot_account_controls (
  broker_account_id uuid PRIMARY KEY
    REFERENCES public.broker_accounts(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  state text NOT NULL DEFAULT 'RUNNING'
    CHECK (state IN ('RUNNING', 'PAUSED', 'STOPPED', 'EMERGENCY_STOPPED')),
  reason text NOT NULL DEFAULT '',
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS robot_account_controls_user_idx
  ON public.robot_account_controls (user_id);

CREATE TABLE IF NOT EXISTS public.robot_control_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_account_id uuid NOT NULL,
  user_id uuid NOT NULL,
  action text NOT NULL,
  state_before text NOT NULL,
  state_after text NOT NULL,
  reason text NOT NULL DEFAULT '',
  actor_id uuid,
  readiness jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS robot_control_events_account_idx
  ON public.robot_control_events (broker_account_id, created_at DESC);

ALTER TABLE public.robot_account_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.robot_account_controls FORCE ROW LEVEL SECURITY;
ALTER TABLE public.robot_control_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.robot_control_events FORCE ROW LEVEL SECURITY;

CREATE POLICY robot_account_controls_select_own
  ON public.robot_account_controls FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());
CREATE POLICY robot_control_events_select_own
  ON public.robot_control_events FOR SELECT TO authenticated
  USING (user_id = public.current_app_user_id());

REVOKE ALL ON TABLE public.robot_account_controls FROM anon;
REVOKE ALL ON TABLE public.robot_control_events FROM anon;
GRANT SELECT ON TABLE public.robot_account_controls TO authenticated;
GRANT SELECT ON TABLE public.robot_control_events TO authenticated;
GRANT ALL ON TABLE public.robot_account_controls TO service_role;
GRANT ALL ON TABLE public.robot_control_events TO service_role;
