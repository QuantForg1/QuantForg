# Phase 4 — AI Trading Intelligence (freeze citation)

**Owner approval:** Product owner ordered Phase 4 AI Trading Intelligence &
Autonomous Strategy Optimization (market intelligence product API, regime
UNCERTAIN taxonomy, signal quality DTO, bounded adaptive proposals, optimizer
orchestrator, AI risk alerts, supervisor mode ladder).

**Authorized freeze touches (gap-only, no redesign):**
- Read-only assembly from existing ITE snapshot / quality / confluence /
  scalping score / regime sources — **no** weight or threshold changes
- Do **not** enable `ADAPTIVE_THRESHOLD_ENABLED` or LIVE adaptive auto-apply
- Risk Center / OMS remain authoritative; AI never overrides kill-switches
- Intelligence/Research UI wiring only (RC4) — no Terminal/Book/Counsel restyle

**Non-goals preserved:**
- No ConfluenceEngine / ITE runtime / scalping scorer rewrite
- No auto-deploy optimized strategies to LIVE
- No automatic risk increases
- No fabricated market data, liquidity, or model accuracy
- No LIVE test `order_send`; no second VPS

**Supervisor default:** `MONITOR_ONLY` until owner configures a higher mode.

**Regression gate:** `pytest -m trading_core` must pass before merge.
