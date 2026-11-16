-- Owner risk baseline 2026-11-16 — Production data change (gate G1).
-- NOT APPLIED. Run only after written owner approval, in one transaction.
-- LIVE trading stays DISABLED; this script never touches live_trading_state.
-- Usage (psql): \set owner_user_id '<owner auth user uuid>'
BEGIN;

-- 1. Saved runtime policy: v16 -> v17. Guarded on the version we audited.
UPDATE public.trading_runtime_config
SET document = (document - 'experimental')
      || jsonb_build_object(
           'max_planned_risk_pct', '9',
           'max_aggregate_open_risk_pct', '9',
           'daily_loss_pct', '25',
           'min_reward_risk', '1.50',
           'preferred_reward_risk', '1.50',
           'max_spread', '0.45',
           'min_trade_quality', 75,
           'max_concurrent_positions', 1,
           'max_lot', '0.01',
           'session_utc', '07:00-17:00 Mon-Fri',
           'experimental_promoted', false),
    version = version + 1,
    updated_at = now()
WHERE id = 1 AND version = 16;

-- 2. Platform (admin) defaults and maxima.
UPDATE public.platform_risk_policy
SET max_planned_risk_pct = 9, default_planned_risk_pct = 9,
    max_aggregate_open_risk_pct = 9, default_aggregate_open_risk_pct = 9,
    max_daily_loss_pct = 25, default_daily_loss_pct = 25,
    max_spread = 0.45, min_trade_quality = 75, min_reward_risk = 1.50,
    notes = 'Owner baseline 2026-11-16: 9/25/RR1.5/0.45/Q75/07-17 Mon-Fri',
    updated_at = now()
WHERE is_active = true;

-- 3. Owner's own saved settings (strictest wins; they were 10% / 48%).
UPDATE public.user_risk_settings
SET planned_risk_pct = 9, aggregate_open_risk_pct = 9, daily_loss_pct = 25,
    updated_at = now()
WHERE user_id = :'owner_user_id'::uuid AND is_active = true;

-- 4. Stale ops overlay: remove ULTRA_AGGRESSIVE and the 20%/48%/5-position values.
UPDATE public.ite_ops_runtime_state
SET payload = jsonb_set(
      jsonb_set(
        jsonb_set(payload - 'risk_profile_id', '{risk_per_trade_pct}', '"9.00"'),
        '{live_trading_risk}',
        (payload->'live_trading_risk')
          || '{"risk_per_trade_pct":"9.0","max_daily_loss_pct":"25.0","min_reward_risk":"1.50","max_spread":"0.45","min_score":"75","max_open_positions":1,"max_total_exposure_pct":"9.00"}'::jsonb
      ),
      '{live_trading_risk,hard_ceiling}',
      '{"risk_per_trade_pct":"9.0","max_daily_loss_pct":"25.00","max_open_positions":1,"max_consecutive_losses":3,"max_total_exposure_pct":"9.00","max_margin_utilization_pct":"40.00"}'::jsonb
    ),
    updated_at = now()
WHERE singleton = true;

-- Verify before COMMIT: exactly one row per statement, LIVE still DISABLED.
SELECT version, document->>'max_planned_risk_pct' AS risk, document->>'daily_loss_pct' AS daily,
       document->>'min_reward_risk' AS rr, document->>'max_spread' AS spread,
       document->>'min_trade_quality' AS quality, document->>'session_utc' AS session
FROM public.trading_runtime_config WHERE id = 1;
SELECT payload->>'live_trading_state' AS live_state FROM public.ite_ops_runtime_state;
-- COMMIT;  -- run manually after checking the output above
