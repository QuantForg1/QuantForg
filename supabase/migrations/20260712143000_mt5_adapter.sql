-- =============================================================================
-- QuantForg migration: MT5 Adapter Sprint 1 (connection history)
-- Version: 20260712143000
-- Reversible: see supabase/migrations/down/20260712143000_mt5_adapter.down.sql
-- Depends on: 20260712120100_domain_tables (users), public.set_updated_at
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.mt5_connections (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  login               bigint NOT NULL CHECK (login > 0),
  server              text NOT NULL,
  status              text NOT NULL DEFAULT 'disconnected'
                        CHECK (status IN (
                          'disconnected', 'initializing', 'connecting',
                          'connected', 'reconnecting', 'error'
                        )),
  session_ref         text NOT NULL DEFAULT '',
  terminal_path       text NOT NULL DEFAULT '',
  terminal_build      integer,
  terminal_version    text NOT NULL DEFAULT '',
  latency_ms          double precision,
  last_heartbeat_at   timestamptz,
  connected           boolean NOT NULL DEFAULT false,
  login_status        text NOT NULL DEFAULT 'logged_out',
  last_error          text NOT NULL DEFAULT '',
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_connections_server_nonempty CHECK (length(trim(server)) > 0),
  CONSTRAINT mt5_connections_last_error_len CHECK (length(last_error) <= 1000),
  CONSTRAINT mt5_connections_terminal_version_len CHECK (length(terminal_version) <= 64)
);

CREATE UNIQUE INDEX IF NOT EXISTS mt5_connections_user_login_server_uidx
  ON public.mt5_connections (user_id, login, server);

CREATE INDEX IF NOT EXISTS mt5_connections_user_id_idx
  ON public.mt5_connections (user_id);
CREATE INDEX IF NOT EXISTS mt5_connections_status_idx
  ON public.mt5_connections (status);
CREATE INDEX IF NOT EXISTS mt5_connections_connected_idx
  ON public.mt5_connections (connected);

CREATE TRIGGER mt5_connections_set_updated_at
  BEFORE UPDATE ON public.mt5_connections
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.mt5_connections IS
  'MT5 terminal connection state (Sprint 1 connection layer). No order data.';

-- Connection history / heartbeat events
CREATE TABLE IF NOT EXISTS public.mt5_connection_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id   uuid NOT NULL
                    REFERENCES public.mt5_connections (id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  event_type      text NOT NULL
                    CHECK (event_type IN (
                      'initialize', 'login', 'connected', 'heartbeat',
                      'reconnect', 'shutdown', 'error'
                    )),
  latency_ms      double precision,
  terminal_build  integer,
  terminal_version text NOT NULL DEFAULT '',
  details         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT mt5_connection_events_type_nonempty
    CHECK (length(trim(event_type)) > 0)
);

CREATE INDEX IF NOT EXISTS mt5_connection_events_connection_id_idx
  ON public.mt5_connection_events (connection_id);
CREATE INDEX IF NOT EXISTS mt5_connection_events_user_id_idx
  ON public.mt5_connection_events (user_id);
CREATE INDEX IF NOT EXISTS mt5_connection_events_created_at_idx
  ON public.mt5_connection_events (created_at DESC);

COMMENT ON TABLE public.mt5_connection_events IS
  'MT5 connection history + heartbeat events (terminal version captured).';
