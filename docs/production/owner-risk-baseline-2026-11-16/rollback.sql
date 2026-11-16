-- Roll back the 2026-11-16 data change to the audited v16 values.
-- The code ceilings in owner_live_limits.py still clamp every value, so a
-- rollback of data alone cannot loosen live limits below the deployed code.
BEGIN;
UPDATE public.trading_runtime_config
SET document = :'v16_document'::jsonb, version = version + 1, updated_at = now()
WHERE id = 1;
UPDATE public.platform_risk_policy
SET max_planned_risk_pct = 20, default_planned_risk_pct = 20,
    max_aggregate_open_risk_pct = 30, default_aggregate_open_risk_pct = 30,
    max_daily_loss_pct = 48, default_daily_loss_pct = 48,
    max_spread = 1.00, min_trade_quality = 70, min_reward_risk = 0.20,
    updated_at = now()
WHERE is_active = true;
UPDATE public.user_risk_settings
SET planned_risk_pct = 10, aggregate_open_risk_pct = 30, daily_loss_pct = 48,
    updated_at = now()
WHERE user_id = :'owner_user_id'::uuid AND is_active = true;
UPDATE public.ite_ops_runtime_state
SET payload = jsonb_set(jsonb_set(payload, '{risk_profile_id}', '"ULTRA_AGGRESSIVE"'),
                        '{risk_per_trade_pct}', '"8.00"')
              || jsonb_build_object('live_trading_risk', :'ops_live_trading_risk'::jsonb),
    updated_at = now()
WHERE singleton = true;
-- :ops_live_trading_risk = ite_ops_runtime_state_payload_keys.live_trading_risk
-- from rollback_pre_apply_state.json. live_trading_state is not changed.
-- COMMIT;
