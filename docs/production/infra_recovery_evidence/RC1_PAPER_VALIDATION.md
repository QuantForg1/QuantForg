# RC1 Validation Report

Generated: `2026-07-31T12:38:49.672987Z`

Institutional Production Validation Pipeline for QuantForg ITE.
This report does **not** modify strategy, Quality/Confidence floors, weights, or risk logic.

- Quality floor (locked): `80`
- Confidence floor (locked): `80`

## Final Recommendation

**NOT READY**

## Infrastructure Health

- **gateway_status:** `UNKNOWN`
- **oms_status:** `UNKNOWN`
- **mt5_status:** `UNKNOWN`
- **ai_status:** `UNKNOWN`
- **crashes:** `0`
- **note:** `offline_pipeline_infrastructure_not_live_probed`

## Replay Results

- **events_processed:** `10`
- **eligible_trades:** `7`
- **rejected_trades:** `3`
- **score_distribution:**
  - **quality:**
    - **80-84:** `4`
    - **85-89:** `2`
    - **90-94:** `1`
  - **confidence:**
    - **80-84:** `4`
    - **85-89:** `2`
    - **90-94:** `1`
- **quality_histogram:**
  - **80-84:** `4`
  - **85-89:** `2`
  - **90-94:** `1`
- **confidence_histogram:**
  - **80-84:** `4`
  - **85-89:** `2`
  - **90-94:** `1`
- **expected_broker_submissions:** 7 items
- **coverage:**
  - **regimes_required:** 4 items
  - **regimes_seen:** 4 items
  - **regimes_missing:** 0 items
  - **sessions_required:** 4 items
  - **sessions_seen:** 4 items
  - **sessions_missing:** 0 items
- **quality_floor:** `80`
- **confidence_floor:** `80`
- **eligible_sample:** 7 items
- **rejected_sample:** 3 items

## Paper Trading Results

- **fills_simulated:** `7`
- **open_positions:** `0`
- **closed_positions:** `7`
- **equity:** `9985.0`
- **drawdown_pct:** `0.2`
- **realized_pnl:** `-15.0`
- **win_rate_pct:** `28.57`
- **loss_rate_pct:** `71.43`
- **profit_factor:** `0.4`
- **expectancy:** `-2.1429`
- **sharpe:** `-1.1619`
- **sortino:** `-1.1339`
- **account:**
  - **starting_equity:** `10000.0`
  - **equity:** `9985.0`
  - **peak_equity:** `10000.0`
  - **max_drawdown_pct:** `0.2`
  - **realized_pnl:** `-15.0`
  - **wins:** `2`
  - **losses:** `5`
  - **gross_profit:** `10.0`
  - **gross_loss:** `25.0`
- **broker_orders_submitted:** `0`

## Shadow Trading Results

- **shadow_orders_recorded:** `0`
- **broker_submissions:** `0`
- **mt5_calls:** `0`

## OMS Statistics

- **status:** `UNKNOWN`
- **latency_note:** `from trade journal`

## Gateway Statistics

- **status:** `UNKNOWN`
- **latency_note:** `from trade journal`

## Risk Statistics

- **daily_loss_enforced:** `True`
- **portfolio_caps_enforced:** `True`
- **correlation_enforced:** `True`
- **emergency_stop_verified:** `True`

## Performance Statistics

- **fills_simulated:** `7`
- **open_positions:** `0`
- **closed_positions:** `7`
- **equity:** `9985.0`
- **drawdown_pct:** `0.2`
- **realized_pnl:** `-15.0`
- **win_rate_pct:** `28.57`
- **loss_rate_pct:** `71.43`
- **profit_factor:** `0.4`
- **expectancy:** `-2.1429`
- **sharpe:** `-1.1619`
- **sortino:** `-1.1339`
- **account:**
  - **starting_equity:** `10000.0`
  - **equity:** `9985.0`
  - **peak_equity:** `10000.0`
  - **max_drawdown_pct:** `0.2`
  - **realized_pnl:** `-15.0`
  - **wins:** `2`
  - **losses:** `5`
  - **gross_profit:** `10.0`
  - **gross_loss:** `25.0`
- **broker_orders_submitted:** `0`

## Acceptance Criteria

- **summary:**
  - **passed:** `17`
  - **failed:** `3`
  - **unknown:** `0`
  - **total:** `20`
  - **hard_fails:** 0 items
  - **infra_unknown:** `False`
- **recommendation:** `NOT READY`
- **gates:** 20 items
- **quality_floor:** `80`
- **confidence_floor:** `80`

## Live Pilot Dashboard Snapshot

- **gateway_health:** `UNKNOWN`
- **mt5_status:** `UNKNOWN`
- **oms_status:** `UNKNOWN`
- **ai_status:** `UNKNOWN`
- **current_session:** `—`
- **current_regime:** `—`
- **eligible_trades:** `7`
- **rejected_trades:** `3`
- **broker_submissions:** `0`
- **fill_rate:** `100.0`
- **win_rate:** `28.57`
- **loss_rate:** `71.43`
- **profit_factor:** `0.4`
- **expectancy:** `-2.1429`
- **average_rr:** `2.0`
- **drawdown:** `0.2`
- **current_equity:** `9985.0`
- **open_positions:** `0`
- **closed_positions:** `7`
- **daily_pnl:** `-15.0`
- **weekly_pnl:** `-15.0`
- **monthly_pnl:** `-15.0`
- **latency:**
  - **oms_ms_avg:** `16.5`
  - **ai_ms_avg:** `44.5`
  - **gateway_ms_avg:** `12.5`

## Rules Affirmation

- Strategy unmodified
- Quality threshold unmodified (80)
- Confidence threshold unmodified (80)
- Weights unmodified
- Risk logic unmodified
- Institutional safety preserved
