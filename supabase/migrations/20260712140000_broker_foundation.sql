-- =============================================================================
-- QuantForg migration: Broker Foundation tables
-- Version: 20260712140000
-- Reversible: see supabase/migrations/down/20260712140000_broker_foundation.down.sql
-- Depends on: public.users, public.brokers, public.set_updated_at
-- =============================================================================

-- Extend catalogue brokers with adapter platform metadata
ALTER TABLE public.brokers
  ADD COLUMN IF NOT EXISTS platform_code text NOT NULL DEFAULT 'other'
    CHECK (platform_code IN ('mt5', 'mt4', 'ctrader', 'dxtrade', 'other'));

ALTER TABLE public.brokers
  ADD COLUMN IF NOT EXISTS description text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS brokers_platform_code_idx
  ON public.brokers (platform_code);

COMMENT ON COLUMN public.brokers.platform_code IS
  'Adapter platform code (mt5/mt4/ctrader/dxtrade/other). No live adapter yet.';
COMMENT ON COLUMN public.brokers.description IS
  'Optional human-readable broker description.';

-- ---------------------------------------------------------------------------
-- broker_capabilities
-- ---------------------------------------------------------------------------
CREATE TABLE public.broker_capabilities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id   uuid NOT NULL REFERENCES public.brokers (id) ON DELETE CASCADE,
  code        text NOT NULL
                CHECK (code IN (
                  'connect', 'disconnect', 'validate', 'refresh',
                  'account_info', 'symbols', 'balances', 'positions', 'orders'
                )),
  enabled     boolean NOT NULL DEFAULT true,
  notes       text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_capabilities_broker_code_uidx UNIQUE (broker_id, code)
);

CREATE INDEX broker_capabilities_broker_id_idx
  ON public.broker_capabilities (broker_id);

CREATE TRIGGER broker_capabilities_set_updated_at
  BEFORE UPDATE ON public.broker_capabilities
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_capabilities IS
  'Advertised adapter capabilities per broker (domain BrokerCapability).';

-- ---------------------------------------------------------------------------
-- broker_accounts
-- ---------------------------------------------------------------------------
CREATE TABLE public.broker_accounts (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_id            uuid NOT NULL REFERENCES public.brokers (id) ON DELETE RESTRICT,
  external_account_id  text NOT NULL,
  label                text NOT NULL DEFAULT '',
  environment          text NOT NULL DEFAULT 'demo'
                         CHECK (environment IN ('demo', 'live')),
  status               text NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'active', 'inactive', 'revoked')),
  server               text NOT NULL DEFAULT '',
  metadata             jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_accounts_external_nonempty
    CHECK (length(trim(external_account_id)) > 0)
);

CREATE UNIQUE INDEX broker_accounts_user_broker_external_uidx
  ON public.broker_accounts (user_id, broker_id, lower(external_account_id))
  WHERE status <> 'revoked';

CREATE INDEX broker_accounts_user_id_idx ON public.broker_accounts (user_id);
CREATE INDEX broker_accounts_broker_id_idx ON public.broker_accounts (broker_id);
CREATE INDEX broker_accounts_status_idx ON public.broker_accounts (status);

CREATE TRIGGER broker_accounts_set_updated_at
  BEFORE UPDATE ON public.broker_accounts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_accounts IS
  'User-linked broker integration accounts (domain BrokerAccount).';

-- ---------------------------------------------------------------------------
-- broker_credentials (encrypted at rest by application layer)
-- ---------------------------------------------------------------------------
CREATE TABLE public.broker_credentials (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_account_id   uuid NOT NULL
                        REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  credential_type     text NOT NULL
                        CHECK (credential_type IN (
                          'password', 'api_key', 'api_secret', 'token', 'certificate'
                        )),
  encrypted_payload   text NOT NULL,
  key_hint            text NOT NULL DEFAULT '',
  rotated_at          timestamptz,
  created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_credentials_payload_nonempty
    CHECK (length(trim(encrypted_payload)) > 0),
  CONSTRAINT broker_credentials_account_type_uidx
    UNIQUE (broker_account_id, credential_type)
);

CREATE INDEX broker_credentials_account_id_idx
  ON public.broker_credentials (broker_account_id);

CREATE TRIGGER broker_credentials_set_updated_at
  BEFORE UPDATE ON public.broker_credentials
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_credentials IS
  'Encrypted broker secrets. Application encrypts; API never returns plaintext.';
COMMENT ON COLUMN public.broker_credentials.encrypted_payload IS
  'Fernet ciphertext produced by core.security.crypto.encrypt_secret.';

-- ---------------------------------------------------------------------------
-- broker_connections
-- ---------------------------------------------------------------------------
CREATE TABLE public.broker_connections (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_account_id     uuid NOT NULL
                          REFERENCES public.broker_accounts (id) ON DELETE CASCADE,
  status                text NOT NULL DEFAULT 'disconnected'
                          CHECK (status IN (
                            'disconnected', 'connecting', 'connected', 'error'
                          )),
  last_connected_at     timestamptz,
  last_error            text NOT NULL DEFAULT '',
  adapter_session_ref   text NOT NULL DEFAULT '',
  created_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT broker_connections_account_uidx UNIQUE (broker_account_id)
);

CREATE INDEX broker_connections_status_idx ON public.broker_connections (status);

CREATE TRIGGER broker_connections_set_updated_at
  BEFORE UPDATE ON public.broker_connections
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.broker_connections IS
  'Adapter connection lifecycle (domain BrokerConnection). No live sessions yet.';
