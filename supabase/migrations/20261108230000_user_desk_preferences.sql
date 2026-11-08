-- =============================================================================
-- QuantForg User Platform: server-persisted desk preferences on user_settings
-- Version: 20261108230000
-- RLS unchanged (existing user_settings policies).
-- =============================================================================

ALTER TABLE public.user_settings
  ADD COLUMN IF NOT EXISTS default_symbol text NOT NULL DEFAULT 'XAUUSD',
  ADD COLUMN IF NOT EXISTS default_timeframe text NOT NULL DEFAULT 'M15',
  ADD COLUMN IF NOT EXISTS date_format text NOT NULL DEFAULT 'ymd',
  ADD COLUMN IF NOT EXISTS time_format text NOT NULL DEFAULT '24h',
  ADD COLUMN IF NOT EXISTS dashboard_prefs jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS trading_ui_prefs jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_date_format_check;

ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_date_format_check
  CHECK (date_format IN ('ymd', 'dmy', 'mdy'));

ALTER TABLE public.user_settings
  DROP CONSTRAINT IF EXISTS user_settings_time_format_check;

ALTER TABLE public.user_settings
  ADD CONSTRAINT user_settings_time_format_check
  CHECK (time_format IN ('24h', '12h'));

COMMENT ON COLUMN public.user_settings.default_symbol IS
  'Default market symbol for desk UI (not execution routing).';

COMMENT ON COLUMN public.user_settings.default_timeframe IS
  'Default chart/timeframe code for desk UI (M15, H1, …).';

COMMENT ON COLUMN public.user_settings.dashboard_prefs IS
  'Opaque dashboard layout/panel preferences (json object).';

COMMENT ON COLUMN public.user_settings.trading_ui_prefs IS
  'Opaque trading desk UI preferences (json object).';
