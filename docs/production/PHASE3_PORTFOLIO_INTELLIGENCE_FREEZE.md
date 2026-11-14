# Phase 3 — Portfolio Intelligence (freeze citation)

**Owner approval:** Product owner ordered Phase 3 Institutional Trading
Intelligence & Portfolio Management (household portfolio, exposure, risk
allocation, strategy analytics, attribution, Book OS wiring).

**Authorized freeze touches (gap-only, no redesign):**
- OMS: thin `broker_submit_block_reason` hook for household new-entry blocks
- Risk / prefs: extend `live_prefs_tighten` for `aggregate_open_risk_pct`
- Portfolio Engine: **call** existing sync as read primitive — do not rewrite
- Book UI: restore Book home + wire panels (RC4 usability only, no restyle)

**Non-goals preserved:**
- No second VPS / multi-LIVE fan-out / lifting one-active-account LIVE uniqueness
- No ITE / AI Decision / Scalping / PME redesign
- No fabricated balances, FX, or `trade_allowed`
- No LIVE test `order_send`
- No auto-close of open positions from new risk rules
- Terminal / Research / Counsel untouched beyond shared chrome

**Regression gate:** `pytest -m trading_core` must pass before merge.
