-- =============================================================================
-- QuantForg migration: Public Live Market Chat
-- Version: 20261110180000
-- Reversible: see supabase/migrations/down/20261110180000_live_market_chat.down.sql
-- Depends on: public.users, public.set_updated_at
-- =============================================================================

CREATE TABLE public.live_market_chat_messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel         text NOT NULL DEFAULT 'xauusd'
                    CHECK (channel ~ '^[a-z0-9_-]{2,32}$'),
  user_id         uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  display_name    text NOT NULL DEFAULT ''
                    CHECK (char_length(display_name) BETWEEN 1 AND 64),
  body            text NOT NULL
                    CHECK (char_length(body) BETWEEN 1 AND 500),
  parent_id       uuid REFERENCES public.live_market_chat_messages (id) ON DELETE SET NULL,
  status          text NOT NULL DEFAULT 'visible'
                    CHECK (status IN ('visible', 'hidden', 'removed')),
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at      timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX live_market_chat_messages_channel_created_idx
  ON public.live_market_chat_messages (channel, created_at DESC)
  WHERE status = 'visible';

CREATE INDEX live_market_chat_messages_user_created_idx
  ON public.live_market_chat_messages (user_id, created_at DESC);

CREATE TRIGGER live_market_chat_messages_set_updated_at
  BEFORE UPDATE ON public.live_market_chat_messages
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.live_market_chat_messages IS
  'Public Live Market discussion feed (TradingView-style). Visible rows are readable without login.';

CREATE TABLE public.live_market_chat_reports (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id      uuid NOT NULL REFERENCES public.live_market_chat_messages (id) ON DELETE CASCADE,
  reporter_id     uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  reason          text NOT NULL DEFAULT 'spam'
                    CHECK (reason IN ('spam', 'abuse', 'off_topic', 'other')),
  note            text NOT NULL DEFAULT ''
                    CHECK (char_length(note) <= 500),
  created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
  UNIQUE (message_id, reporter_id)
);

COMMENT ON TABLE public.live_market_chat_reports IS
  'Authenticated moderation reports for Live Market Chat messages.';
