-- =============================================================================
-- DOWN: 20260712120000_extensions_helpers
-- Removes shared trigger helpers. Extension is left installed (shared dependency).
-- =============================================================================

DROP FUNCTION IF EXISTS public.forbid_mutation() CASCADE;
DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;

-- pgcrypto may be used by other schemas; do not DROP EXTENSION here.
