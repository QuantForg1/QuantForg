# Phase 6 — Institutional Intelligence (freeze citation)

**Owner approval:** Product owner ordered Phase 6 Institutional Intelligence,
Predictive Analytics & Performance Optimization.

**Authorized freeze touches (gap-only, no redesign):**
- Read-mostly `/institutional-intelligence` facade over ATI, Phase 5 ops, IRAP,
  QPM, execution quality, QDIE and report catalogs
- Ops-classified UI routes + `/intelligence-center` hub — no new trader-rail desks
- Recommendation lifecycle is governance-only; Approved ≠ LIVE
- RC4 inheritance for ops shells — no Terminal/Book/Counsel restyle

**Non-goals preserved:**
- No new ML training pipelines or provider swaps
- No `order_send`, `FORCE_FIRST_TRADE`, kill-switch bypass
- No automatic LIVE deploy, auto-rebalance, or risk-limit increases
- No fabricated prices, balances, fills or forecast guarantees
- No second MT5 host; Weltrade LIVE path preserved

**Defaults:** `advisory_only`, `never_guarantees_forecasts`, `approved_is_not_live`.

**Regression gate:** `pytest -m trading_core` must pass before merge.
