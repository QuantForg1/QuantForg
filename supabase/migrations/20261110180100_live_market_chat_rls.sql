-- =============================================================================
-- QuantForg migration: Live Market Chat RLS
-- Version: 20261110180100
-- Reversible: see supabase/migrations/down/20261110180100_live_market_chat_rls.down.sql
-- Depends on: 20261110180000_live_market_chat, public.current_app_user_id
-- =============================================================================

ALTER TABLE public.live_market_chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.live_market_chat_messages FORCE ROW LEVEL SECURITY;

-- Public read of approved messages (anon + authenticated).
CREATE POLICY live_market_chat_messages_select_public
  ON public.live_market_chat_messages
  FOR SELECT
  TO anon, authenticated
  USING (status = 'visible');

-- Authenticated users may insert only as themselves.
CREATE POLICY live_market_chat_messages_insert_own
  ON public.live_market_chat_messages
  FOR INSERT
  TO authenticated
  WITH CHECK (
    user_id = public.current_app_user_id()
    AND status = 'visible'
  );

-- Authors may soft-hide their own message (status -> hidden/removed).
CREATE POLICY live_market_chat_messages_update_own
  ON public.live_market_chat_messages
  FOR UPDATE
  TO authenticated
  USING (user_id = public.current_app_user_id())
  WITH CHECK (
    user_id = public.current_app_user_id()
    AND status IN ('visible', 'hidden', 'removed')
  );

-- No client deletes — moderation uses status updates / service_role.
REVOKE DELETE ON public.live_market_chat_messages FROM anon, authenticated;

ALTER TABLE public.live_market_chat_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.live_market_chat_reports FORCE ROW LEVEL SECURITY;

CREATE POLICY live_market_chat_reports_insert_own
  ON public.live_market_chat_reports
  FOR INSERT
  TO authenticated
  WITH CHECK (reporter_id = public.current_app_user_id());

CREATE POLICY live_market_chat_reports_select_own
  ON public.live_market_chat_reports
  FOR SELECT
  TO authenticated
  USING (reporter_id = public.current_app_user_id());

GRANT SELECT ON public.live_market_chat_messages TO anon, authenticated;
GRANT INSERT, UPDATE ON public.live_market_chat_messages TO authenticated;
GRANT SELECT, INSERT ON public.live_market_chat_reports TO authenticated;
