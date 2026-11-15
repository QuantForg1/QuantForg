# Phase 8 — Quantitative Research & Strategy Factory (freeze citation)

**Owner approval:** Product owner ordered Phase 8 Advanced Quantitative Research
& Strategy Factory (QRSF / `quantitative_research_control`).

**Authorized freeze touches (gap-only, no redesign):**
- Read-mostly `/quantitative-research-control` facade composing QSF, Quant Studio,
  Research Validation, backtests/walk-forward/Monte Carlo, ISLM, Phase 6–7 intel
- Ops-classified UI routes — no flagship `/research` OS redesign
- Research experiment/approval mutations are governance-only, never LIVE
- RC4 inheritance for ops shells
- Deep links to existing `/quantforg-strategy-factory`, lifecycle, Phase 7 Autonomy

**Non-goals preserved:**
- No `order_send` from Phase 8; never auto LIVE deploy
- No executing arbitrary AI-generated code in Production
- No fabricating OHLCV / Sharpe / profitability claims without evidence
- No auto-promote of optimized parameters
- Distinct from historical Multi-account Phase 8 worker/dispatch namespace
- Do not replace/delete existing `/quantforg-strategy-factory`

**Regression gate:** `pytest -m trading_core` must pass before merge.
