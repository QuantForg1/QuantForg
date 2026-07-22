-- Live account risk state — peak equity high-water mark (drawdown gates).
-- Daily PnL is computed from MT5 history deals; peak must persist across restarts.
-- Version: 20260722180000

CREATE TABLE IF NOT EXISTS public.live_account_risk_state (
  login            bigint PRIMARY KEY,
  user_id          uuid REFERENCES public.users (id) ON DELETE SET NULL,
  peak_equity      numeric(24, 8) NOT NULL CHECK (peak_equity >= 0),
  last_equity      numeric(24, 8) NOT NULL CHECK (last_equity >= 0),
  session_day      date NOT NULL,
  updated_at       timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at       timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS live_account_risk_state_user_id_idx
  ON public.live_account_risk_state (user_id);

COMMENT ON TABLE public.live_account_risk_state IS
  'Persisted peak equity HWM for live risk drawdown gates (XAUUSD).';
