-- Per-user risk profiles (owner decision 2026-11-18).
-- One row per user. `settings` holds only the fields the user customised;
-- every other field resolves to the approved defaults in the backend
-- (risk 15%, aggregate 20%, daily 30%, weekly/monthly/drawdown OFF,
-- net RR 1.50, spread 1.00, max lot 0.50, 5 positions, quality 75, 24/5).
-- Writes go through the backend (service role) with optimistic versioning.
-- Users may read their own row and their own change history only.
-- Additive: no existing table or row is modified.

CREATE TABLE IF NOT EXISTS public.user_risk_profiles (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(settings) = 'object'),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    schema_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_by UUID
);

COMMENT ON TABLE public.user_risk_profiles IS
  'Per-user risk profile overrides. Missing keys = approved defaults. Backend writes only.';

CREATE TABLE IF NOT EXISTS public.user_risk_profile_events (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    actor_id UUID,
    action TEXT NOT NULL CHECK (action IN ('update', 'reset', 'migrate')),
    before JSONB NOT NULL DEFAULT '{}'::jsonb,
    after JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS user_risk_profile_events_user_created_idx
    ON public.user_risk_profile_events (user_id, created_at DESC);

ALTER TABLE public.user_risk_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_risk_profile_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.user_risk_profiles FROM anon, authenticated;
REVOKE ALL ON TABLE public.user_risk_profile_events FROM anon, authenticated;
GRANT SELECT ON TABLE public.user_risk_profiles TO authenticated;
GRANT SELECT ON TABLE public.user_risk_profile_events TO authenticated;
GRANT ALL ON TABLE public.user_risk_profiles TO service_role;
GRANT ALL ON TABLE public.user_risk_profile_events TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.user_risk_profile_events_id_seq TO service_role;

DROP POLICY IF EXISTS user_risk_profiles_select_own ON public.user_risk_profiles;
CREATE POLICY user_risk_profiles_select_own ON public.user_risk_profiles
    FOR SELECT TO authenticated USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_risk_profile_events_select_own ON public.user_risk_profile_events;
CREATE POLICY user_risk_profile_events_select_own ON public.user_risk_profile_events
    FOR SELECT TO authenticated USING (user_id = auth.uid());
