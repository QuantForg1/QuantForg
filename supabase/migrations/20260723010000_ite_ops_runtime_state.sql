-- Durable Ops runtime singleton — survives Railway redeploys without a volume.
-- Never fabricates LIVE; only stores what OWNER officially promoted.

CREATE TABLE IF NOT EXISTS public.ite_ops_runtime_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.ite_ops_runtime_state IS
  'ITE Ops mode + auto-trading run state — durable across API restarts.';

ALTER TABLE public.ite_ops_runtime_state ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.ite_ops_runtime_state FROM anon, authenticated;
GRANT ALL ON TABLE public.ite_ops_runtime_state TO service_role;

INSERT INTO public.ite_ops_runtime_state (singleton, payload)
VALUES (TRUE, '{}'::jsonb)
ON CONFLICT (singleton) DO NOTHING;
