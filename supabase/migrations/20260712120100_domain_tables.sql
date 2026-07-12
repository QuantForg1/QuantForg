-- =============================================================================
-- QuantForg migration: domain tables (Sprint foundation schema)
-- Version: 20260712120100
-- Source of truth: app/domain/entities/*
-- Reversible: see supabase/migrations/down/20260712120100_domain_tables.down.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE public.users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_user_id    uuid UNIQUE,
  email           text NOT NULL,
  display_name    text NOT NULL,
  role            text NOT NULL DEFAULT 'trader'
                    CHECK (role IN ('owner', 'admin', 'trader', 'viewer', 'support')),
  status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'active', 'suspended', 'deactivated')),
  password_hash   text NOT NULL DEFAULT '',
  last_login_at   timestamptz,
  deactivated_at  timestamptz,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT users_email_nonempty CHECK (length(trim(email)) > 0),
  CONSTRAINT users_display_name_nonempty CHECK (length(trim(display_name)) > 0),
  CONSTRAINT users_deactivated_consistency CHECK (
    (status = 'deactivated' AND deactivated_at IS NOT NULL)
    OR (status <> 'deactivated')
  )
);

CREATE UNIQUE INDEX users_email_uidx ON public.users (lower(email));
CREATE INDEX users_status_idx ON public.users (status);
CREATE INDEX users_auth_user_id_idx ON public.users (auth_user_id)
  WHERE auth_user_id IS NOT NULL;

CREATE TRIGGER users_set_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Optional FK to auth.users when the Auth schema is present (Supabase).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'auth' AND table_name = 'users'
  ) THEN
    ALTER TABLE public.users
      ADD CONSTRAINT users_auth_user_id_fkey
      FOREIGN KEY (auth_user_id) REFERENCES auth.users (id) ON DELETE SET NULL;
  END IF;
END $$;

COMMENT ON TABLE public.users IS 'Platform identity aggregate (domain User).';
COMMENT ON COLUMN public.users.auth_user_id IS
  'Optional link to Supabase Auth auth.users.id for RLS.';

-- ---------------------------------------------------------------------------
-- brokers
-- ---------------------------------------------------------------------------
CREATE TABLE public.brokers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  slug          text NOT NULL,
  broker_type   text NOT NULL DEFAULT 'retail'
                  CHECK (broker_type IN (
                    'retail', 'prime', 'ecn', 'market_maker', 'prop', 'other'
                  )),
  status        text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'active', 'inactive', 'blocked')),
  country_code  char(2) NOT NULL,
  website       text NOT NULL DEFAULT '',
  created_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at    timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT brokers_name_nonempty CHECK (length(trim(name)) > 0),
  CONSTRAINT brokers_slug_nonempty CHECK (length(trim(slug)) > 0),
  CONSTRAINT brokers_country_code_format CHECK (country_code ~ '^[A-Z]{2}$')
);

CREATE UNIQUE INDEX brokers_slug_uidx ON public.brokers (lower(slug));
CREATE INDEX brokers_status_idx ON public.brokers (status);

CREATE TRIGGER brokers_set_updated_at
  BEFORE UPDATE ON public.brokers
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.brokers IS 'Broker catalogue (domain Broker).';

-- ---------------------------------------------------------------------------
-- licenses
-- ---------------------------------------------------------------------------
CREATE TABLE public.licenses (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  tier        text NOT NULL
                CHECK (tier IN ('trial', 'starter', 'professional', 'enterprise')),
  status      text NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                  'pending', 'active', 'expired', 'revoked', 'suspended'
                )),
  seats       integer NOT NULL DEFAULT 1 CHECK (seats BETWEEN 1 AND 10000),
  issued_at   timestamptz NOT NULL DEFAULT timezone('utc', now()),
  expires_at  timestamptz,
  revoked_at  timestamptz,
  notes       text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at  timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX licenses_user_id_idx ON public.licenses (user_id);
CREATE INDEX licenses_status_idx ON public.licenses (status);

CREATE TRIGGER licenses_set_updated_at
  BEFORE UPDATE ON public.licenses
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.licenses IS 'Commercial entitlement (domain License).';

-- ---------------------------------------------------------------------------
-- symbols
-- ---------------------------------------------------------------------------
CREATE TABLE public.symbols (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code             text NOT NULL,
  name             text NOT NULL,
  asset_class      text NOT NULL DEFAULT 'forex'
                     CHECK (asset_class IN (
                       'forex', 'metals', 'indices', 'commodities',
                       'crypto', 'stocks', 'other'
                     )),
  status           text NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'suspended', 'delisted')),
  base_currency    text NOT NULL,
  quote_currency   text NOT NULL,
  digits           integer NOT NULL DEFAULT 5 CHECK (digits BETWEEN 0 AND 8),
  pip_size         numeric(20, 10) NOT NULL CHECK (pip_size > 0),
  broker_id        uuid REFERENCES public.brokers (id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT symbols_code_nonempty CHECK (length(trim(code)) > 0),
  CONSTRAINT symbols_name_nonempty CHECK (length(trim(name)) > 0),
  CONSTRAINT symbols_base_currency_nonempty CHECK (length(trim(base_currency)) > 0),
  CONSTRAINT symbols_quote_currency_nonempty CHECK (length(trim(quote_currency)) > 0)
);

CREATE UNIQUE INDEX symbols_code_broker_uidx
  ON public.symbols (lower(code), coalesce(broker_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE INDEX symbols_status_idx ON public.symbols (status);
CREATE INDEX symbols_broker_id_idx ON public.symbols (broker_id)
  WHERE broker_id IS NOT NULL;

CREATE TRIGGER symbols_set_updated_at
  BEFORE UPDATE ON public.symbols
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.symbols IS 'Tradable instrument catalogue (domain Symbol).';

-- ---------------------------------------------------------------------------
-- trading_accounts
-- ---------------------------------------------------------------------------
CREATE TABLE public.trading_accounts (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  broker_id        uuid NOT NULL REFERENCES public.brokers (id) ON DELETE RESTRICT,
  account_number   text NOT NULL,
  account_type     text NOT NULL DEFAULT 'demo'
                     CHECK (account_type IN ('demo', 'live', 'contest')),
  status           text NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'active', 'suspended', 'closed')),
  currency         text NOT NULL DEFAULT 'USD',
  leverage         integer NOT NULL DEFAULT 100 CHECK (leverage >= 1),
  balance_amount   numeric(20, 8) NOT NULL DEFAULT 0 CHECK (balance_amount >= 0),
  balance_currency text NOT NULL DEFAULT 'USD',
  label            text NOT NULL DEFAULT '',
  closed_at        timestamptz,
  created_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT trading_accounts_account_number_nonempty
    CHECK (length(trim(account_number)) > 0),
  CONSTRAINT trading_accounts_currency_match
    CHECK (currency = balance_currency),
  CONSTRAINT trading_accounts_closed_consistency CHECK (
    (status = 'closed' AND closed_at IS NOT NULL)
    OR (status <> 'closed')
  )
);

CREATE UNIQUE INDEX trading_accounts_broker_account_uidx
  ON public.trading_accounts (broker_id, lower(account_number));
CREATE INDEX trading_accounts_user_id_idx ON public.trading_accounts (user_id);
CREATE INDEX trading_accounts_status_idx ON public.trading_accounts (status);

CREATE TRIGGER trading_accounts_set_updated_at
  BEFORE UPDATE ON public.trading_accounts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.trading_accounts IS
  'User account at a broker (domain TradingAccount).';

-- ---------------------------------------------------------------------------
-- trading_sessions
-- ---------------------------------------------------------------------------
CREATE TABLE public.trading_sessions (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trading_account_id   uuid NOT NULL
                         REFERENCES public.trading_accounts (id) ON DELETE CASCADE,
  user_id              uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  status               text NOT NULL DEFAULT 'active'
                         CHECK (status IN (
                           'active', 'idle', 'closed', 'expired', 'terminated'
                         )),
  started_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  ended_at             timestamptz,
  last_seen_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  client_label         text NOT NULL DEFAULT '',
  termination_reason   text NOT NULL DEFAULT '',
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT trading_sessions_ended_consistency CHECK (
    (status IN ('closed', 'expired', 'terminated') AND ended_at IS NOT NULL)
    OR (status IN ('active', 'idle'))
  )
);

CREATE INDEX trading_sessions_account_idx ON public.trading_sessions (trading_account_id);
CREATE INDEX trading_sessions_user_id_idx ON public.trading_sessions (user_id);
CREATE INDEX trading_sessions_status_idx ON public.trading_sessions (status);

CREATE TRIGGER trading_sessions_set_updated_at
  BEFORE UPDATE ON public.trading_sessions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.trading_sessions IS
  'Connection window to a trading account (domain TradingSession).';

-- ---------------------------------------------------------------------------
-- strategy_metadata
-- ---------------------------------------------------------------------------
CREATE TABLE public.strategy_metadata (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL,
  slug              text NOT NULL,
  version           text NOT NULL,
  strategy_type     text NOT NULL DEFAULT 'custom'
                      CHECK (strategy_type IN (
                        'trend', 'mean_reversion', 'breakout',
                        'scalping', 'grid', 'custom'
                      )),
  status            text NOT NULL DEFAULT 'draft'
                      CHECK (status IN (
                        'draft', 'published', 'deprecated', 'archived'
                      )),
  owner_user_id     uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  description       text NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
  parameter_schema  jsonb NOT NULL DEFAULT '{}'::jsonb,
  tags              text[] NOT NULL DEFAULT '{}'::text[]
                      CHECK (cardinality(tags) <= 20),
  created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT strategy_metadata_name_nonempty CHECK (length(trim(name)) > 0),
  CONSTRAINT strategy_metadata_slug_nonempty CHECK (length(trim(slug)) > 0),
  CONSTRAINT strategy_metadata_version_nonempty CHECK (length(trim(version)) > 0)
);

CREATE UNIQUE INDEX strategy_metadata_slug_version_uidx
  ON public.strategy_metadata (lower(slug), lower(version));
CREATE INDEX strategy_metadata_owner_idx ON public.strategy_metadata (owner_user_id);
CREATE INDEX strategy_metadata_status_idx ON public.strategy_metadata (status);

CREATE TRIGGER strategy_metadata_set_updated_at
  BEFORE UPDATE ON public.strategy_metadata
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.strategy_metadata IS
  'Strategy catalogue entry (domain StrategyMetadata); not strategy logic.';

-- ---------------------------------------------------------------------------
-- risk_profiles
-- ---------------------------------------------------------------------------
CREATE TABLE public.risk_profiles (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trading_account_id    uuid REFERENCES public.trading_accounts (id) ON DELETE CASCADE,
  risk_level            text NOT NULL DEFAULT 'moderate'
                          CHECK (risk_level IN (
                            'conservative', 'moderate', 'aggressive', 'custom'
                          )),
  max_risk_per_trade    numeric(8, 4) NOT NULL DEFAULT 1.0
                          CHECK (max_risk_per_trade >= 0 AND max_risk_per_trade <= 100),
  max_daily_loss        numeric(8, 4) NOT NULL DEFAULT 5.0
                          CHECK (max_daily_loss >= 0 AND max_daily_loss <= 100),
  max_open_positions    integer NOT NULL DEFAULT 5
                          CHECK (max_open_positions BETWEEN 1 AND 500),
  max_leverage          integer NOT NULL DEFAULT 100 CHECK (max_leverage >= 1),
  is_active             boolean NOT NULL DEFAULT true,
  label                 text NOT NULL DEFAULT '',
  created_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at            timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX risk_profiles_user_id_idx ON public.risk_profiles (user_id);
CREATE INDEX risk_profiles_account_idx ON public.risk_profiles (trading_account_id)
  WHERE trading_account_id IS NOT NULL;
CREATE UNIQUE INDEX risk_profiles_one_active_per_user_account_uidx
  ON public.risk_profiles (user_id, coalesce(trading_account_id, '00000000-0000-0000-0000-000000000000'::uuid))
  WHERE is_active;

CREATE TRIGGER risk_profiles_set_updated_at
  BEFORE UPDATE ON public.risk_profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.risk_profiles IS
  'Declared risk limits (domain RiskProfile); not a risk engine.';

-- ---------------------------------------------------------------------------
-- orders
-- ---------------------------------------------------------------------------
CREATE TABLE public.orders (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trading_account_id   uuid NOT NULL
                         REFERENCES public.trading_accounts (id) ON DELETE CASCADE,
  symbol_id            uuid NOT NULL REFERENCES public.symbols (id) ON DELETE RESTRICT,
  order_type           text NOT NULL
                         CHECK (order_type IN (
                           'market', 'limit', 'stop', 'stop_limit'
                         )),
  side                 text NOT NULL CHECK (side IN ('buy', 'sell')),
  quantity             numeric(20, 8) NOT NULL CHECK (quantity > 0),
  status               text NOT NULL DEFAULT 'pending'
                         CHECK (status IN (
                           'pending', 'accepted', 'partially_filled', 'filled',
                           'cancelled', 'rejected', 'expired'
                         )),
  time_in_force        text NOT NULL DEFAULT 'gtc'
                         CHECK (time_in_force IN ('gtc', 'ioc', 'fok', 'day')),
  limit_price          numeric(20, 8) CHECK (limit_price IS NULL OR limit_price >= 0),
  stop_price           numeric(20, 8) CHECK (stop_price IS NULL OR stop_price >= 0),
  stop_loss            numeric(20, 8) CHECK (stop_loss IS NULL OR stop_loss >= 0),
  take_profit          numeric(20, 8) CHECK (take_profit IS NULL OR take_profit >= 0),
  filled_quantity      numeric(20, 8) CHECK (filled_quantity IS NULL OR filled_quantity >= 0),
  average_fill_price   numeric(20, 8)
                         CHECK (average_fill_price IS NULL OR average_fill_price >= 0),
  submitted_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
  closed_at            timestamptz,
  client_order_id      text NOT NULL DEFAULT '',
  rejection_reason     text NOT NULL DEFAULT '',
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX orders_account_idx ON public.orders (trading_account_id);
CREATE INDEX orders_symbol_idx ON public.orders (symbol_id);
CREATE INDEX orders_status_idx ON public.orders (status);
CREATE INDEX orders_submitted_at_idx ON public.orders (submitted_at DESC);

CREATE TRIGGER orders_set_updated_at
  BEFORE UPDATE ON public.orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.orders IS 'Order intent aggregate (domain Order).';

-- ---------------------------------------------------------------------------
-- positions
-- ---------------------------------------------------------------------------
CREATE TABLE public.positions (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trading_account_id   uuid NOT NULL
                         REFERENCES public.trading_accounts (id) ON DELETE CASCADE,
  symbol_id            uuid NOT NULL REFERENCES public.symbols (id) ON DELETE RESTRICT,
  side                 text NOT NULL CHECK (side IN ('long', 'short')),
  quantity             numeric(20, 8) NOT NULL CHECK (quantity > 0),
  open_price           numeric(20, 8) NOT NULL CHECK (open_price >= 0),
  status               text NOT NULL DEFAULT 'open'
                         CHECK (status IN ('open', 'partially_closed', 'closed')),
  stop_loss            numeric(20, 8) CHECK (stop_loss IS NULL OR stop_loss >= 0),
  take_profit          numeric(20, 8) CHECK (take_profit IS NULL OR take_profit >= 0),
  opened_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  closed_at            timestamptz,
  close_price          numeric(20, 8) CHECK (close_price IS NULL OR close_price >= 0),
  opening_order_id     uuid REFERENCES public.orders (id) ON DELETE SET NULL,
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT positions_closed_consistency CHECK (
    (status = 'closed' AND closed_at IS NOT NULL AND close_price IS NOT NULL)
    OR (status <> 'closed')
  )
);

CREATE INDEX positions_account_idx ON public.positions (trading_account_id);
CREATE INDEX positions_symbol_idx ON public.positions (symbol_id);
CREATE INDEX positions_status_idx ON public.positions (status);
CREATE INDEX positions_opening_order_idx ON public.positions (opening_order_id)
  WHERE opening_order_id IS NOT NULL;

CREATE TRIGGER positions_set_updated_at
  BEFORE UPDATE ON public.positions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.positions IS 'Open market exposure (domain Position).';

-- ---------------------------------------------------------------------------
-- trades (immutable ledger)
-- ---------------------------------------------------------------------------
CREATE TABLE public.trades (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trading_account_id   uuid NOT NULL
                         REFERENCES public.trading_accounts (id) ON DELETE CASCADE,
  symbol_id            uuid NOT NULL REFERENCES public.symbols (id) ON DELETE RESTRICT,
  side                 text NOT NULL CHECK (side IN ('buy', 'sell')),
  quantity             numeric(20, 8) NOT NULL CHECK (quantity > 0),
  price                numeric(20, 8) NOT NULL CHECK (price >= 0),
  executed_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
  order_id             uuid REFERENCES public.orders (id) ON DELETE SET NULL,
  position_id          uuid REFERENCES public.positions (id) ON DELETE SET NULL,
  commission_amount    numeric(20, 8) CHECK (commission_amount IS NULL OR commission_amount >= 0),
  commission_currency  text,
  swap_amount          numeric(20, 8),
  swap_currency        text,
  realized_pnl_amount  numeric(20, 8),
  realized_pnl_currency text,
  external_trade_id    text NOT NULL DEFAULT '',
  created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX trades_account_idx ON public.trades (trading_account_id);
CREATE INDEX trades_symbol_idx ON public.trades (symbol_id);
CREATE INDEX trades_executed_at_idx ON public.trades (executed_at DESC);
CREATE INDEX trades_order_idx ON public.trades (order_id) WHERE order_id IS NOT NULL;
CREATE INDEX trades_position_idx ON public.trades (position_id) WHERE position_id IS NOT NULL;

CREATE TRIGGER trades_forbid_update
  BEFORE UPDATE ON public.trades
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

CREATE TRIGGER trades_forbid_delete
  BEFORE DELETE ON public.trades
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

COMMENT ON TABLE public.trades IS
  'Immutable fill/ledger record (domain Trade).';

-- ---------------------------------------------------------------------------
-- signals
-- ---------------------------------------------------------------------------
CREATE TABLE public.signals (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol_id              uuid NOT NULL REFERENCES public.symbols (id) ON DELETE RESTRICT,
  direction              text NOT NULL CHECK (direction IN ('buy', 'sell', 'neutral')),
  source                 text NOT NULL DEFAULT 'manual'
                           CHECK (source IN ('manual', 'system', 'external', 'strategy')),
  status                 text NOT NULL DEFAULT 'pending'
                           CHECK (status IN (
                             'pending', 'active', 'consumed', 'expired', 'cancelled'
                           )),
  confidence             numeric(8, 6) CHECK (
                           confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
                         ),
  entry_price            numeric(20, 8) CHECK (entry_price IS NULL OR entry_price >= 0),
  stop_loss              numeric(20, 8) CHECK (stop_loss IS NULL OR stop_loss >= 0),
  take_profit            numeric(20, 8) CHECK (take_profit IS NULL OR take_profit >= 0),
  strategy_metadata_id   uuid REFERENCES public.strategy_metadata (id) ON DELETE SET NULL,
  trading_account_id     uuid REFERENCES public.trading_accounts (id) ON DELETE SET NULL,
  generated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
  expires_at             timestamptz,
  consumed_at            timestamptz,
  notes                  text NOT NULL DEFAULT '',
  created_at             timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at             timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX signals_symbol_idx ON public.signals (symbol_id);
CREATE INDEX signals_status_idx ON public.signals (status);
CREATE INDEX signals_account_idx ON public.signals (trading_account_id)
  WHERE trading_account_id IS NOT NULL;
CREATE INDEX signals_strategy_idx ON public.signals (strategy_metadata_id)
  WHERE strategy_metadata_id IS NOT NULL;

CREATE TRIGGER signals_set_updated_at
  BEFORE UPDATE ON public.signals
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.signals IS
  'Time-bounded direction suggestion record (domain Signal).';

-- ---------------------------------------------------------------------------
-- audit_logs (immutable)
-- ---------------------------------------------------------------------------
CREATE TABLE public.audit_logs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action          text NOT NULL
                    CHECK (action IN (
                      'create', 'read', 'update', 'delete', 'login', 'logout',
                      'activate', 'deactivate', 'suspend', 'revoke', 'submit',
                      'cancel', 'export', 'system'
                    )),
  outcome         text NOT NULL CHECK (outcome IN ('success', 'failure', 'denied')),
  resource_type   text NOT NULL CHECK (length(trim(resource_type)) > 0
                    AND length(resource_type) <= 64),
  resource_id     uuid,
  actor_user_id   uuid REFERENCES public.users (id) ON DELETE SET NULL,
  occurred_at     timestamptz NOT NULL DEFAULT timezone('utc', now()),
  ip_address      text NOT NULL DEFAULT '',
  user_agent      text NOT NULL DEFAULT '' CHECK (length(user_agent) <= 512),
  message         text NOT NULL DEFAULT '' CHECK (length(message) <= 1000),
  metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX audit_logs_actor_idx ON public.audit_logs (actor_user_id)
  WHERE actor_user_id IS NOT NULL;
CREATE INDEX audit_logs_resource_idx ON public.audit_logs (resource_type, resource_id);
CREATE INDEX audit_logs_occurred_at_idx ON public.audit_logs (occurred_at DESC);

CREATE TRIGGER audit_logs_forbid_update
  BEFORE UPDATE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

CREATE TRIGGER audit_logs_forbid_delete
  BEFORE DELETE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

COMMENT ON TABLE public.audit_logs IS
  'Append-only forensic event log (domain AuditLog).';
