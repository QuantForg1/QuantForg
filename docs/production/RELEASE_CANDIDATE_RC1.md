# Release Candidate RC1 — Production Readiness

Feature completeness (v1–v10) is frozen for trading capability. RC1 proves **profitability, stability, and safety** with measurable evidence before capital scale-up.

## Hard locks

| Lock | Value |
|------|-------|
| Smoke places real trades | **Never** |
| Auto-scale capital | **Never** |
| Mix Paper / Demo / Live | **Never** |
| New strategies / experimental production | **Out of scope** |

## Surfaces

| Module | Behaviour |
|--------|-----------|
| Production Checklist | MT5, Broker, OMS, AI, Portfolio, Recovery, Health, Retry, Dashboard, Railway, Secrets, DB, Market Data → PASS / WARNING / FAIL |
| Smoke Test | Gateway, login, symbols, margin, spread, order validation, position sync — **no order_send** |
| Live Statistics | Trades, WR, DD, PF, RR, PnL, latency, slippage, risk, calibration |
| Performance Reports | Daily / Weekly / Monthly + CSV / PDF-text |
| RC Validation | Consecutive days, uptime, latency, rejects, retries |
| Go Live Score | 0–100; recommend scale-up only above configurable threshold (default 80) |
| Venue Stats | Paper / Demo / Live isolated |
| Capital Advisor | Recommendations only |
| Docs | Operator, Deployment, Recovery, Incident, Monitoring, Maintenance |

## API / UI

- `GET /ite/reliability/rc1?current_capital=200`
- `POST /ite/reliability/rc1/smoke`
- `POST /ite/reliability/rc1/reports/{daily|weekly|monthly}`
- Desk: `/rc1`

## Reuse (no rewrite)

Composes production hardening, reliability platform, AI validation, performance lab, portfolio intelligence, ITE probes. Does **not** duplicate PRR or launch readiness — those remain canonical for institutional audit / promotion gates.

## Guides

Generated under `docs/production/rc1_guides/`.

## Tests

`tests/unit/test_release_candidate_rc1.py`
