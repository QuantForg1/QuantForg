# Strategy Runtime Engine Report

**Status:** Complete  
**Scope:** Strategy Runtime orchestration — **trading decisions only**  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Enabling `EXECUTION_ENABLED` (remains **false**)  
- Calling `order_send()`  
- AI / ML signal generation  
- Live strategy execution / order placement  

Broker Foundation, MT5 Sprints 1–4, Execution Safety, Portfolio Engine, Risk Engine, Auth, User Platform, Supabase, and CI are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Pipeline: collect → freshness → preconditions → decision | Yes |
| Decisions: **NO_ACTION** / **WATCH** / **READY** / **BLOCKED** | Yes |
| `StrategySignal` (direction, confidence, reasons, timeframe, symbol, generated_at) | Yes |
| Events: StrategyEvaluated / SignalGenerated / SignalRejected / StrategyBlocked | Yes |
| Consumes Market Context, Structure, Liquidity, OB, FVG (via `AnalysisContext`) | Yes |
| Consumes MT5 market data, Portfolio, Risk Engine | Yes |
| `POST /api/v1/strategy/evaluate` | Yes |
| `GET /api/v1/strategy/signals` | Yes |
| Persist evaluations, signals, decision history + RLS | Yes |
| Tests + CI green | Yes |

---

## Architecture

```
POST /api/v1/strategy/evaluate
        ↓
EvaluateStrategyUseCase
        ↓
StrategyRuntimeService.evaluate
  1. collect market state (MT5 + portfolio + AnalysisContext)
  2. validate data freshness
  3. evaluate strategy preconditions (confluence)
  4. generate StrategyDecision (+ optional StrategySignal)
  5. optional Risk Engine consult on READY → may BLOCK + reject signal
        ↓
strategy_evaluations / strategy_signals / strategy_decision_history
```

Pipeline position relative to trading stack:

```
Analysis Engines → Strategy Runtime → Risk Engine → Execution Safety → Execution Gateway (flag-gated)
```

**Never executes. Never enables `EXECUTION_ENABLED`. Never calls `order_send()`.**

---

## Decision types

| Decision | Meaning |
|----------|---------|
| `no_action` | No actionable setup |
| `watch` | Partial confluence — monitor |
| `ready` | Confluence met — signal generated (still no execution) |
| `blocked` | Stale data, market closed, or risk reject |

---

## Inputs consumed

| Source | How |
|--------|-----|
| Market Context | `market_open`, `session` on `AnalysisContext` |
| Market Structure | `structure_bias` (up / down / range / unknown) |
| Liquidity | bullish/bearish sweep flags |
| Order Blocks | bullish/bearish OB flags |
| Fair Value Gaps | bullish/bearish FVG flags |
| MT5 Market Data | tick age, last price, candle count via `MT5MarketDataService` |
| Portfolio | equity / positions via `PortfolioSyncService` when connected |
| Risk Engine | consulted on `READY` when `check_risk=true` |

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/strategy/evaluate` | decision, preconditions, market_state, optional signal, risk fields |
| `GET` | `/api/v1/strategy/signals` | list of StrategySignals for the current user |

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712150000_strategy_runtime.sql` | `strategy_evaluations`, `strategy_signals`, `strategy_decision_history` |
| `20260712150100_strategy_runtime_rls.sql` | Owner RLS (select/insert own) |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No execution records.**

---

## Modules

| Layer | Path |
|-------|------|
| Enums | `app/domain/enums/strategy.py` (`StrategyDecisionType`) |
| Entities | `app/domain/entities/strategy_runtime.py` |
| Events | `app/domain/events/strategy.py` |
| Service | `app/application/services/strategy_runtime.py` |
| Use cases | `app/application/use_cases/strategy_runtime.py` |
| DTOs / schemas | `app/application/dto/strategy_runtime.py`, `app/presentation/schemas/strategy.py` |
| Router | `app/presentation/routers/strategy.py` |
| Persistence | `app/infrastructure/persistence/memory_strategy.py` |
| DI | `core/di/container.py` (`strategy_runtime`, `strategy_uow_factory`) |

---

## Testing / CI

- Mock MT5 used for market-data collection path  
- Asserts `execution_enabled is False` and `order_send` returns disabled retcode  
- **ruff** / **black** / **mypy** — green  
- **pytest** — **269 passed**, 2 skipped, ~79% coverage  

---

## Stop line

Strategy Runtime is complete.  
**Do not** implement AI.  
**Do not** enable execution.  
**Do not** call `order_send()`.
