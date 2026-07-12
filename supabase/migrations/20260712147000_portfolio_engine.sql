-- =============================================================================
-- QuantForg migration: Portfolio & Position Engine (snapshots / history cache)
-- Version: 20260712147000
-- Reversible: see supabase/migrations/down/20260712147000_portfolio_engine.down.sql
-- Depends on: users
-- NOTE: Snapshots and history cache only — no execution records, no credentials.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.portfolio_syncs (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  login                 bigint NOT NULL,
  balance               text NOT NULL DEFAULT '0',
  equity                text NOT NULL DEFAULT '0',
  margin                text NOT NULL DEFAULT '0',
  free_margin           text NOT NULL DEFAULT '0',
  margin_level          text NOT NULL DEFAULT '0',
  profit                text NOT NULL DEFAULT '0',
  leverage              integer NOT NULL DEFAULT 1,
  position_count        integer NOT NULL DEFAULT 0,
  pending_order_count   integer NOT NULL DEFAULT 0,
  history_order_count   integer NOT NULL DEFAULT 0,
  history_deal_count    integer NOT NULL DEFAULT 0,
  snapshot              jsonb NOT NULL DEFAULT '{}'::jsonb,
  synced_at             timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT portfolio_syncs_login_positive CHECK (login > 0),
  CONSTRAINT portfolio_syncs_counts_nonneg CHECK (
    position_count >= 0
    AND pending_order_count >= 0
    AND history_order_count >= 0
    AND history_deal_count >= 0
  )
);

CREATE INDEX IF NOT EXISTS portfolio_syncs_user_id_idx
  ON public.portfolio_syncs (user_id);
CREATE INDEX IF NOT EXISTS portfolio_syncs_synced_at_idx
  ON public.portfolio_syncs (synced_at DESC);

CREATE TABLE IF NOT EXISTS public.portfolio_history_cache (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  kind            text NOT NULL CHECK (kind IN ('order', 'deal')),
  ticket          bigint NOT NULL,
  symbol          text NOT NULL,
  payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at     timestamptz NOT NULL DEFAULT timezone('utc', now()),
  cached_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT portfolio_history_cache_symbol_nonempty CHECK (length(trim(symbol)) > 0),
  CONSTRAINT portfolio_history_cache_ticket_positive CHECK (ticket > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS portfolio_history_cache_user_kind_ticket_uidx
  ON public.portfolio_history_cache (user_id, kind, ticket);
CREATE INDEX IF NOT EXISTS portfolio_history_cache_user_id_idx
  ON public.portfolio_history_cache (user_id);
CREATE INDEX IF NOT EXISTS portfolio_history_cache_occurred_at_idx
  ON public.portfolio_history_cache (occurred_at DESC);

COMMENT ON TABLE public.portfolio_syncs IS
  'Portfolio sync snapshots (read-only). No credentials. No execution.';
COMMENT ON TABLE public.portfolio_history_cache IS
  'Cached MT5 history orders/deals. No credentials. No execution.';
