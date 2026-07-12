-- =============================================================================
-- QuantForg development seed data
-- Loaded only by `supabase db reset` (see config.toml [db.seed]).
-- DO NOT run against production. Fixed UUIDs for deterministic local tests.
-- =============================================================================

-- Catalogue: broker
INSERT INTO public.brokers (
  id, name, slug, broker_type, status, country_code, website
) VALUES (
  '22222222-2222-4222-8222-222222222222',
  'QuantForg Demo Broker',
  'qf-demo-broker',
  'retail',
  'active',
  'US',
  'https://example.local/broker'
);

-- Dev user (not linked to auth.users — set auth_user_id after local signup)
INSERT INTO public.users (
  id, email, display_name, role, status, password_hash
) VALUES (
  '11111111-1111-4111-8111-111111111111',
  'dev@quantforg.local',
  'Dev Trader',
  'trader',
  'active',
  ''
);

-- License
INSERT INTO public.licenses (
  id, user_id, tier, status, seats, expires_at, notes
) VALUES (
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  'professional',
  'active',
  3,
  timezone('utc', now()) + interval '365 days',
  'Development seed license'
);

-- Symbols
INSERT INTO public.symbols (
  id, code, name, asset_class, status, base_currency, quote_currency,
  digits, pip_size, broker_id
) VALUES
(
  '44444444-4444-4444-8444-444444444401',
  'EURUSD',
  'Euro / US Dollar',
  'forex',
  'active',
  'EUR',
  'USD',
  5,
  0.0001,
  '22222222-2222-4222-8222-222222222222'
),
(
  '44444444-4444-4444-8444-444444444402',
  'XAUUSD',
  'Gold / US Dollar',
  'metals',
  'active',
  'XAU',
  'USD',
  2,
  0.01,
  '22222222-2222-4222-8222-222222222222'
);

-- Trading account
INSERT INTO public.trading_accounts (
  id, user_id, broker_id, account_number, account_type, status,
  currency, leverage, balance_amount, balance_currency, label
) VALUES (
  '55555555-5555-4555-8555-555555555555',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  'DEMO-10001',
  'demo',
  'active',
  'USD',
  100,
  10000.00000000,
  'USD',
  'Local demo account'
);

-- Trading session
INSERT INTO public.trading_sessions (
  id, trading_account_id, user_id, status, client_label
) VALUES (
  '66666666-6666-4666-8666-666666666666',
  '55555555-5555-4555-8555-555555555555',
  '11111111-1111-4111-8111-111111111111',
  'active',
  'seed-client'
);

-- Strategy metadata
INSERT INTO public.strategy_metadata (
  id, name, slug, version, strategy_type, status, owner_user_id,
  description, parameter_schema, tags
) VALUES (
  '77777777-7777-4777-8777-777777777777',
  'Seed Breakout',
  'seed-breakout',
  '0.1.0',
  'breakout',
  'draft',
  '11111111-1111-4111-8111-111111111111',
  'Development-only strategy catalogue entry.',
  '{"lookback": {"type": "integer", "default": 20}}'::jsonb,
  ARRAY['seed', 'dev']::text[]
);

-- Risk profile
INSERT INTO public.risk_profiles (
  id, user_id, trading_account_id, risk_level,
  max_risk_per_trade, max_daily_loss, max_open_positions, max_leverage,
  is_active, label
) VALUES (
  '88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  '55555555-5555-4555-8555-555555555555',
  'moderate',
  1.0,
  5.0,
  5,
  100,
  true,
  'Default demo risk'
);

-- Sample order (pending — no fill)
INSERT INTO public.orders (
  id, trading_account_id, symbol_id, order_type, side, quantity,
  status, time_in_force, limit_price, client_order_id
) VALUES (
  '99999999-9999-4999-8999-999999999901',
  '55555555-5555-4555-8555-555555555555',
  '44444444-4444-4444-8444-444444444401',
  'limit',
  'buy',
  0.10,
  'pending',
  'gtc',
  1.08000000,
  'seed-order-1'
);

-- Sample signal
INSERT INTO public.signals (
  id, symbol_id, direction, source, status, confidence,
  entry_price, stop_loss, take_profit, strategy_metadata_id,
  trading_account_id, notes
) VALUES (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
  '44444444-4444-4444-8444-444444444401',
  'buy',
  'strategy',
  'pending',
  0.720000,
  1.08100000,
  1.07500000,
  1.09000000,
  '77777777-7777-4777-8777-777777777777',
  '55555555-5555-4555-8555-555555555555',
  'Seed signal for local UI/dev checks'
);

-- Audit log (append-only)
INSERT INTO public.audit_logs (
  id, action, outcome, resource_type, resource_id, actor_user_id, message, metadata
) VALUES (
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1',
  'system',
  'success',
  'seed',
  '11111111-1111-4111-8111-111111111111',
  '11111111-1111-4111-8111-111111111111',
  'Development seed applied',
  '{"env": "development"}'::jsonb
);
