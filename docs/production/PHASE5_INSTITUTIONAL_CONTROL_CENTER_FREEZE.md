# Phase 5 — Institutional Control Center (freeze citation)

**Owner approval:** Product owner ordered Phase 5 Autonomous Trading Operations
& Institutional Control Center (seven ops modules + aggregator API).

**Authorized freeze touches (gap-only, no redesign):**
- Read-mostly `/institutional-ops` facade over existing AOC / ISLM / IRDP /
  execution intelligence / multi-account / risk / incidents / audit
- Ops-classified UI routes only — no new trader-rail desks
- Robot controls call existing `/trading/robot/{start,pause,stop}` only
- RC4 token inheritance for new ops shells — no Terminal/Book/Counsel restyle

**Non-goals preserved:**
- No parallel OMS / Trading Core / PME / ITE runtime rewrite
- No `order_send`, `FORCE_FIRST_TRADE`, or kill-switch bypass
- No automatic LIVE strategy deployment
- No risk limit increases; AI cannot override hard constraints
- No second MT5 host / VPS; Weltrade LIVE path preserved
- No fabricated balances, `trade_allowed`, or execution success metrics

**Defaults:** `observe_only`, `human_approval_required`, `never_auto_deploy_live`.

**Regression gate:** `pytest -m trading_core` must pass before merge.
