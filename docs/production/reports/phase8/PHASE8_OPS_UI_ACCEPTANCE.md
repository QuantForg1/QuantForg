# Phase 8 — Ops UI acceptance

**Date:** 2026-11-15  
**Merge:** `3697ce30` (PR #293)  
**Frontend:** www.quantforg.com → `frontend-63y27kutk-quantforg.vercel.app`  
**Backend:** Railway production `3697ce30`

## Route acceptance (unauthenticated HTTP)

| Route | Status |
|---|---|
| `/quant-research` | 200 |
| `/strategy-factory` | 200 |
| `/research-data` | 200 |
| `/strategy-backtesting` | 200 |
| `/strategy-optimization` | 200 |
| `/research-leaderboard` | 200 |
| `/research-governance` | 200 |
| `/quantforg-strategy-factory` (deep link) | 200 |
| `/autonomous-trading` (Phase 7 deep link) | 200 |

## API acceptance

| Endpoint | Unauth |
|---|---|
| `/api/v1/quantitative-research-control/health` | 401 |
| `/api/v1/quantitative-research-control/summary` | 401 |
| `/api/v1/quantitative-research-control/validation/pipeline` | 401 |

## Safety spot-check

- No LIVE orders placed during acceptance
- Isolation model `phase8-research-1.0.0` present on facade
- Research-only defaults unchanged; Weltrade LIVE path preserved
