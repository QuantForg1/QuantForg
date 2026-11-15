# Phase 7 — Autonomous Trading Control (freeze citation)

**Owner approval:** Product owner ordered Phase 7 Autonomous Trading Intelligence
& Controlled Execution.

**Authorized freeze touches (gap-only, no redesign):**
- Read-mostly `/autonomous-trading-control` facade over Phase 4–6 intel,
  AutoTradePolicy, RiskEngine facts, OMS auth preview, live-trading status
- Ops-classified UI routes — no new trader-rail desks / Terminal redesign
- Modes default OBSERVE_ONLY; Mode 2 is intent + eligibility preview only
- Mutations that touch robot/LIVE/ops must proxy existing endpoints only
- RC4 inheritance for ops shells

**Non-goals preserved:**
- No `order_send` from Phase 7; `phase7_live_dispatch=false`
- No FORCE_FIRST_TRADE re-arm; no forced `trade_allowed=true`
- No risk-limit increases; no second OMS / MT5 host
- Distinct from historical Multi-account Phase 7 ops namespace

**Regression gate:** `pytest -m trading_core` must pass before merge.
