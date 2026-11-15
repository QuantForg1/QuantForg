# Phase 8 — Quantitative Research & Strategy Factory delivery report

**Branch:** `feat/phase8-quantitative-research-control`  
**Freeze citation:** `docs/production/PHASE8_QUANTITATIVE_RESEARCH_CONTROL_FREEZE.md`  
**Model:** `phase8-research-1.0.0`

## Summary

Phase 8 productizes a research-only Quantitative Research Control facade behind
`/quantitative-research-control` and seven ops desks. Composes existing QSF /
Quant Studio / RVP / backtest / walk-forward / Monte Carlo / ISLM / Phase 6–7
surfaces. Never order_send. Never auto LIVE deploy.

## Modules

1. `/quant-research` — projects / experiments hub
2. `/strategy-factory` — templates + AI hypothesize + QSF deep link
3. `/research-data` — data quality / availability
4. `/strategy-backtesting` — backtest + walk-forward + Monte Carlo
5. `/strategy-optimization` — optimization + robustness
6. `/research-leaderboard` — risk-adjusted ranking + validation classes
7. `/research-governance` — 10-stage pipeline + approvals + audit

## Backend

- Domain: `app/domain/quantitative_research_control/`
- Service: `app/application/services/quantitative_research_control.py`
- Router: `/quantitative-research-control`
- Database: **no new migrations** (in-process ResearchStore)

## Safety

- `research_only` / `never_order_send` / `never_auto_live_deploy`
- `never_executes_arbitrary_code` / `never_fabricates_ohlcv`
- `backtest_is_not_live` / `approved_is_not_live` / `paper_is_not_live`
- Material param change invalidates prior approval
- Distinct from Multi-account Phase 8 worker/dispatch track

## Tests

- `tests/unit/test_phase8_quantitative_research_control.py`
- `frontend/src/lib/trading/phase8-research-contract.test.ts`
- Gates: ruff, black, mypy, unit, `pytest -m trading_core`, `tsc --noEmit`, production build

## Production verify

_Filled after merge / Railway + Vercel verification._
