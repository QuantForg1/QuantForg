-- =============================================================================
-- QuantForg migration: Broker Foundation Sprint 1 (sessions + credential status)
-- Version: 20260712141000
-- Reversible: see supabase/migrations/down/20260712141000_broker_sessions.down.sql
-- Depends on: 20260712140000_broker_foundation, public.set_updated_at
-- =============================================================================

-- Credential lifecycle status (encryption-ready payload already exists)
ALTER TABLE public.broker_credentials
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'rotated', 'revoked', 'expired'));

CREATE INDEX IF NOT EXISTS broker_credentials_status_idx
  ON public.broker_credentials (status);

COMMENT ON COLUMN public.broker_credentials.status IS
  'Credential lifecycle (active/rotated/revoked/expired). Payload remains ciphertext.';

-- ---------------------------------------------------------------------------
-- broker_sessions
-- ---------------------------------------------------------------------------
CREATE TABLE public.broker_sessions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_account_id   uuid NOT NULL
                        REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  connection_id       uuid NOT NULL
                        REFERENCES public.broker_connections (id) ON DELETE CASCADE,
  session_ref         text NOT NULL,
  status              text NOT NULL DEFAULT 'connected'
                        CHECK (status IN (
                          'disconnected', 'connecting', 'connected', 'error'
                        )),
  expires_at          timestamptz,
  last_refreshed_at   timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_sessions_ref_nonempty CHECK (length(trim(session_ref)) > 0)
);

CREATE INDEX broker_sessions_account_id_idx
  ON public.broker_sessions (broker_account_id);
CREATE INDEX broker_sessions_connection_id_idx
  ON public.broker_sessions (connection_id);
CREATE INDEX broker_sessions_status_idx
  ON public.broker_sessions (status);
CREATE UNIQUE INDEX broker_sessions_active_account_uidx
  ON public.broker_sessions (broker_account_id)
  WHERE status = 'connected';

CREATE TRIGGER broker_sessions_set_updated_at
  BEFORE UPDATE ON public.broker_sessions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_sessions IS
  'Adapter session metadata (domain BrokerSession). No live sockets.';
