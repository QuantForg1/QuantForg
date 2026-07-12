-- =============================================================================
-- QuantForg migration: extensions & shared helpers
-- Version: 20260712120000
-- Reversible: see supabase/migrations/down/20260712120000_extensions_helpers.down.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Bump updated_at on row modification (used by mutable domain tables).
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  NEW.updated_at = timezone('utc', now());
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.set_updated_at() IS
  'Maintains updated_at timestamptz on UPDATE for mutable domain tables.';

-- Block UPDATE/DELETE on append-only ledger tables.
CREATE OR REPLACE FUNCTION public.forbid_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  RAISE EXCEPTION '% is append-only; % is not allowed',
    TG_TABLE_NAME, TG_OP
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

COMMENT ON FUNCTION public.forbid_mutation() IS
  'Raises on UPDATE/DELETE for immutable tables (trades, audit_logs).';
