# RC1 Validation Report

Generated: `2026-07-31T12:31:16.217260Z`

Institutional Production Validation Pipeline for QuantForg ITE.
This report does **not** modify strategy, Quality/Confidence floors, weights, or risk logic.

- Quality floor (locked): `80`
- Confidence floor (locked): `80`

## Final Recommendation

**NOT READY**

## Infrastructure Health

- **api_base:** `https://quantforg-production.up.railway.app`
- **frontend:** `https://www.quantforg.com`
- **collected_at:** `2026-07-31T12:31:16.215362Z`
- **gateway_status:** `UNKNOWN`
- **oms_status:** `UNKNOWN`
- **mt5_status:** `UNKNOWN`
- **ai_status:** `UNKNOWN`
- **gateway_health:** `UNKNOWN`
- **process_health:** `HEALTHY`
- **postgres:** `healthy`
- **redis:** `disabled`
- **environment:** `production`
- **api_version:** `1.0.0`
- **crashes:** `0`
- **auth_blocked_endpoints:** 4 items
- **rc1_endpoint_deployed:** `False`
- **probes:** 13 items
- **evidence_integrity:**
  - **never_fabricated_gateway_oms_mt5_ai:** `True`
  - **auth_required_for_ops_health:** `True`
  - **note:** `Gateway / OMS / MT5 / AI detailed health requires operator bearer token. Public probes only prove process + postgres.`

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

- **shadow_orders_recorded:** `7`
- **broker_submissions:** `0`
- **mt5_calls:** `0`

## OMS Statistics

- **status:** `UNKNOWN`
- **auth_required:** `True`

## Gateway Statistics

- **status:** `UNKNOWN`
- **auth_required:** `True`

## Risk Statistics

- **status:** `UNKNOWN`
- **note:** `requires authenticated ops probe`

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
  - **paper:**
    - **passed:** `8`
    - **failed:** `3`
    - **unknown:** `9`
    - **total:** `20`
    - **hard_fails:** 0 items
    - **infra_unknown:** `False`
  - **shadow:**
    - **passed:** `8`
    - **failed:** `3`
    - **unknown:** `9`
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

## Live Evidence Attachment

- Collected at: `2026-07-31T12:31:16.215362Z`
- API base: `https://quantforg-production.up.railway.app`
- Process health: `HEALTHY`
- Postgres: `healthy`
- Redis: `disabled`
- Gateway: `UNKNOWN` (auth required — not fabricated)
- OMS: `UNKNOWN` (auth required — not fabricated)
- MT5: `UNKNOWN` (auth required — not fabricated)
- AI: `UNKNOWN` (auth required — not fabricated)
- RC1 ops endpoint deployed on production: `False`

Probe artifacts:
- `docs/production/pre_live_evidence/live_health_probes.json`
- `docs/production/pre_live_evidence/rc1_paper_result.json`
- `docs/production/pre_live_evidence/rc1_shadow_result.json`

## Pre-Live Checklist Outcome

**Final recommendation: NOT READY**

Deployment must STOP while any acceptance gate remains UNKNOWN/FAIL.
