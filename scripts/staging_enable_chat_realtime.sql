-- Staging-only: enable Realtime fanout for Live Market Chat.
-- Safe on empty staging; does not touch production.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'live_market_chat_messages'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.live_market_chat_messages';
  END IF;
END $$;
