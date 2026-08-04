-- Operator Symbol Management — durable enable/disable + priority for trading universe.
-- UI/API/Settings only. Does not alter Trading Core, OMS, Gateway, or MT5.

CREATE TABLE IF NOT EXISTS public.symbol_management (
    symbol TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    favorite BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL DEFAULT 1000,
    asset_class TEXT NOT NULL DEFAULT 'other',
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS symbol_management_enabled_priority_idx
    ON public.symbol_management (enabled DESC, priority ASC, symbol ASC);

CREATE INDEX IF NOT EXISTS symbol_management_asset_class_idx
    ON public.symbol_management (asset_class);

COMMENT ON TABLE public.symbol_management IS
  'Owner/Admin trading-universe preferences — enable, favorite, scan priority.';

ALTER TABLE public.symbol_management ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.symbol_management FROM anon, authenticated;
GRANT ALL ON TABLE public.symbol_management TO service_role;
