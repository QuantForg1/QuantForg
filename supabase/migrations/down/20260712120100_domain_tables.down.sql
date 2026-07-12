-- =============================================================================
-- DOWN: 20260712120100_domain_tables
-- Drops domain tables in reverse dependency order (children first).
-- Does NOT use TRUNCATE, DROP DATABASE, or DROP SCHEMA.
-- =============================================================================

DROP TABLE IF EXISTS public.audit_logs CASCADE;
DROP TABLE IF EXISTS public.signals CASCADE;
DROP TABLE IF EXISTS public.trades CASCADE;
DROP TABLE IF EXISTS public.positions CASCADE;
DROP TABLE IF EXISTS public.orders CASCADE;
DROP TABLE IF EXISTS public.risk_profiles CASCADE;
DROP TABLE IF EXISTS public.strategy_metadata CASCADE;
DROP TABLE IF EXISTS public.trading_sessions CASCADE;
DROP TABLE IF EXISTS public.trading_accounts CASCADE;
DROP TABLE IF EXISTS public.symbols CASCADE;
DROP TABLE IF EXISTS public.licenses CASCADE;
DROP TABLE IF EXISTS public.brokers CASCADE;
DROP TABLE IF EXISTS public.users CASCADE;
