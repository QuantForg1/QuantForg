# Quant AI V2.0 — Architecture & Production Readiness

## What it is

**Quant AI** is an institutional **trading intelligence** module.

It is **not** an auto-trading bot.

- Never opens / closes / modifies orders
- Never calls `order_send`
- Never bypasses `EXECUTION_ENABLED`
- Never invents market, portfolio, risk, or execution facts

## Architecture

```
Frontend /quant-ai
    │  React Query (45s refresh, 12s stale)
    ▼
GET /api/v1/quant-ai/dashboard|symbol|portfolio|risk|execution
POST /api/v1/quant-ai/trade-review
    │
    ▼
QuantAIService (application)
    ├─ MT5 status + symbols + ticks + OHLC
    ├─ Portfolio sync (account / positions / deals)
    ├─ MarketContextEngine (session / liquidity / vol)
    ├─ NewsIntelligence (configured feeds only)
    ├─ Execution attempts UoW (read)
    └─ Paper history (fallback fills only)
    │
    ▼
Domain (app/domain/quant_ai/)
    ├─ market_structure.py   — trend / momentum / S-R / WHY / advisory SL-TP
    ├─ portfolio_ai.py       — win rate / RR / expectancy / journal mistakes
    ├─ risk_ai.py            — leverage / margin / correlation / DD flags
    ├─ execution_ai.py       — score over real attempts + slippage
    └─ correlation.py        — pearson on real closes
```

### Security contracts (response flags)

Every payload includes:

- `autonomous_trading: false`
- `advisory_only: true`
- `never_submits_orders: true`
- `never_bypasses_execution_enabled: true`
- `execution_enabled` mirrored from settings (never flipped here)

### Data policy

Sources only: MT5 · broker · execution attempts · portfolio · market data · risk facts · history.

Unavailable → honest `status: unavailable` (no mock / placeholder / fake / demo).

## Locked surfaces (untouched)

MT5 Gateway · Broker Workspace · Trading Terminal · OMS · Institutional Execution Engine ·
TradingSessionProvider · Strategy Engine · Portfolio Intelligence · Execution Intelligence ·
Risk Engine · Auth · existing APIs · DB schema.

## Files changed (new + wiring)

### Backend (new)

- `app/domain/quant_ai/` (package)
- `app/application/services/quant_ai.py`
- `app/presentation/dependencies/quant_ai.py`
- `app/presentation/routers/quant_ai.py`
- `tests/unit/test_quant_ai.py`

### Backend (wiring only)

- `app/main.py` — register `quant_ai` router
- `app/presentation/routers/__init__.py`

### Frontend

- `frontend/src/app/(app)/quant-ai/page.tsx`
- `frontend/src/lib/api/endpoints.ts` — `quantAiApi`
- `frontend/src/components/layout/nav-config.ts` — Quant AI nav
- `frontend/e2e/quant-ai.spec.ts`
- `frontend/e2e/helpers.ts` — TS narrowing for E2E credentials

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/quant-ai/dashboard` | Full intelligence snapshot |
| GET | `/quant-ai/symbol/{symbol}` | WHY brief + MTF |
| GET | `/quant-ai/portfolio` | Portfolio AI |
| GET | `/quant-ai/risk` | Risk AI |
| GET | `/quant-ai/execution` | Execution AI |
| POST | `/quant-ai/trade-review` | Per-trade labels (advisory) |

## Performance

| Layer | Mechanism |
|-------|-----------|
| Backend | `TtlCache` 15s shared dashboard cache |
| Frontend | React Query `staleTime: 12_000`, `refetchInterval: 45_000`, single query key `["quant-ai-dashboard", focus]` |
| Sampling | Majors quote sample (8 symbols) — no full catalogue fan-out |
| Policy | No duplicate polling of locked modules |

## Validation

| Gate | Result |
|------|--------|
| pytest `tests/unit` | 419 passed · coverage ≥ 60% |
| frontend typecheck | pass |
| frontend lint | (see CI log) |
| frontend build | (see CI log) |
| E2E chromium | Quant AI auth + advisory surface |

## Production readiness checklist

- [x] Analysis-only surface — no execution path
- [x] `EXECUTION_ENABLED` never mutated
- [x] No mock market/portfolio/risk/execution data
- [x] Nav entry + dedicated page
- [x] Explainable WHY / confidence / advisory SL-TP
- [x] Portfolio / Risk / Execution / Trade Review panels
- [x] Market dashboard widgets (movers, vol, trends, spreads, heatmap, events)
- [x] React Query caching
- [x] Unit tests for domain analyzers
- [x] E2E auth gate + authenticated load
