# Phase 8 — Quantitative Research & Strategy Factory delivery report

**PR:** https://github.com/QuantForg1/QuantForg/pull/293 — **MERGED** 2026-11-15  
**Merge commit:** `3697ce30`  
**Branch:** `feat/phase8-quantitative-research-control`  
**Freeze citation:** `docs/production/PHASE8_QUANTITATIVE_RESEARCH_CONTROL_FREEZE.md`  
**Model:** `phase8-research-1.0.0`

## Production verify

| Surface | Result |
|---|---|
| Railway `/api/v1/health` | **200** |
| Railway `/api/v1/version` | production `git_commit` = `3697ce30…` |
| Railway `/api/v1/quantitative-research-control/health` | **401** without auth (route live) |
| Railway `/api/v1/quantitative-research-control/summary` | **401** without auth |
| Railway `/api/v1/quantitative-research-control/validation/pipeline` | **401** without auth |
| `www.quantforg.com/login` | **200** |
| `www.quantforg.com/quant-research` | **200** |
| `www.quantforg.com/strategy-factory` | **200** |
| `www.quantforg.com/research-data` | **200** |
| `www.quantforg.com/strategy-backtesting` | **200** |
| `www.quantforg.com/strategy-optimization` | **200** |
| `www.quantforg.com/research-leaderboard` | **200** |
| `www.quantforg.com/research-governance` | **200** |
| `www.quantforg.com/quantforg-strategy-factory` | **200** |
| `www.quantforg.com/autonomous-trading` | **200** |
| Vercel Production frontend | Ready (`frontend-63y27kutk…`); www aliased |
| LIVE test orders | **not performed** |
| Research defaults | research-only / never_order_send / never_auto_live_deploy |

## CI

GitHub Actions (lint, typecheck, unit, trading_core, frontend, integration): **SUCCESS**  
Vercel preview for `frontend` hit Pro rate-limit on the PR; production deploy verified post-merge.

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

- `tests/unit/test_phase8_quantitative_research_control.py` — 10 passed
- `frontend/src/lib/trading/phase8-research-contract.test.ts` — ok
- `pytest -m trading_core` — 2186 passed, 3 xfailed (local); CI SUCCESS
- `tsc --noEmit` — clean
