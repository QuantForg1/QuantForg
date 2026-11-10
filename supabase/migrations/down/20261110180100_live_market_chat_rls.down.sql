DROP POLICY IF EXISTS live_market_chat_reports_select_own ON public.live_market_chat_reports;
DROP POLICY IF EXISTS live_market_chat_reports_insert_own ON public.live_market_chat_reports;
DROP POLICY IF EXISTS live_market_chat_messages_update_own ON public.live_market_chat_messages;
DROP POLICY IF EXISTS live_market_chat_messages_insert_own ON public.live_market_chat_messages;
DROP POLICY IF EXISTS live_market_chat_messages_select_public ON public.live_market_chat_messages;

ALTER TABLE public.live_market_chat_reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.live_market_chat_messages DISABLE ROW LEVEL SECURITY;
