-- =============================================================================
-- QuantForg migration: Broker Foundation Sprint 2 (health + encryption version)
-- Version: 20260712142000
-- Reversible: see supabase/migrations/down/20260712142000_broker_health.down.sql
-- Depends on: 20260712141000_broker_sessions, public.set_updated_at
-- =============================================================================

-- Credential encryption key version (AES-256-GCM envelope also embeds version)
ALTER TABLE public.broker_credentials
  ADD COLUMN IF NOT EXISTS encryption_key_version integer NOT NULL DEFAULT 1;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'broker_credentials_encryption_key_version_check'
  ) THEN
    ALTER TABLE public.broker_credentials
      ADD CONSTRAINT broker_credentials_encryption_key_version_check
      CHECK (encryption_key_version >= 1);
  END IF;
END $$;

COMMENT ON COLUMN public.broker_credentials.encryption_key_version IS
  'AES-256-GCM key version used for encrypted_payload (rotation support).';

-- Expand advertised capability codes (Sprint 2 discovery)
ALTER TABLE public.broker_capabilities
  DROP CONSTRAINT IF EXISTS broker_capabilities_code_check;

ALTER TABLE public.broker_capabilities
  ADD CONSTRAINT broker_capabilities_code_check
  CHECK (code IN (
    'connect', 'disconnect', 'validate', 'refresh',
    'account_info', 'symbols', 'balances', 'positions', 'orders',
    'market_data', 'history'
  ));

-- ---------------------------------------------------------------------------
-- broker_connection_health
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.broker_connection_health (
  id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id                   uuid NOT NULL UNIQUE
                                    REFERENCES public.broker_connections (id)
                                    ON DELETE CASCADE,
  broker_account_id               uuid NOT NULL
                                    REFERENCES public.broker_accounts (id)
                                    ON DELETE CASCADE,
  broker_id                       uuid NOT NULL
                                    REFERENCES public.brokers (id)
                                    ON DELETE CASCADE,
  status                          text NOT NULL DEFAULT 'unknown'
                                    CHECK (status IN (
                                      'healthy', 'degraded', 'unhealthy', 'unknown'
                                    )),
  latency_ms                      double precision,
  last_heartbeat_at               timestamptz,
  last_successful_connection_at   timestamptz,
  reconnect_attempts              integer NOT NULL DEFAULT 0
                                    CHECK (reconnect_attempts >= 0),
  connected_since                 timestamptz,
  last_error                      text NOT NULL DEFAULT '',
  uptime_seconds                  double precision NOT NULL DEFAULT 0,
  created_at                      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at                      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_connection_health_last_error_len
    CHECK (length(last_error) <= 1000)
);

CREATE INDEX IF NOT EXISTS broker_connection_health_broker_id_idx
  ON public.broker_connection_health (broker_id);
CREATE INDEX IF NOT EXISTS broker_connection_health_account_id_idx
  ON public.broker_connection_health (broker_account_id);
CREATE INDEX IF NOT EXISTS broker_connection_health_status_idx
  ON public.broker_connection_health (status);

CREATE TRIGGER broker_connection_health_set_updated_at
  BEFORE UPDATE ON public.broker_connection_health
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_connection_health IS
  'Connection health metrics (latency, heartbeat, uptime, reconnects). No live sockets.';
