# Backtesting Engine Report

**Status:** Complete  
**Scope:** Deterministic event-driven **offline** backtesting  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Enabling `EXECUTION_ENABLED` (remains **false**)  
- Calling `order_send()`  
- Connecting to a live broker  
- AI / ML  
- Live trade placement  

Strategy Runtime, Risk Engine, Execution Safety/Gateway, MT5 Adapter, Broker Foundation, Auth, User Platform, Supabase, and CI are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Historical Replay (candle / tick) | Yes |
| Virtual clock + speed / pause / resume / step | Yes |
| Simulation via Strategy Runtime + Risk + Execution Safety | Yes |
| Virtual Portfolio (equity, balance, floating/realized P/L, margin, DD) | Yes |
| Simulated trades (entry/exit/SL/TP/fees/spread/slippage) | Yes |
| Metrics (return, CAGR, Sharpe, Sortino, PF, expectancy, win rate, avg R, max DD, recovery) | Yes |
| Equity / balance / drawdown curves | Yes |
| Events: Started / Finished / TradeSimulated / MetricUpdated | Yes |
| `POST /api/v1/backtests/run` | Yes |
| `GET /api/v1/backtests` | Yes |
| `GET /api/v1/backtests/{id}` | Yes |
| Persist runs, trades, metrics, equity curves + RLS | Yes |
| Tests + CI green | Yes |

---

## Architecture

```
POST /api/v1/backtests/run
        ↓
RunBacktestUseCase
        ↓
BacktestEngine.run
  HistoricalReplayEngine (virtual clock)
        ↓ per bar/tick
  manage open SL/TP → mark-to-market
  StrategyRuntime.evaluate (offline overrides)
  optional ExecutionSafety.evaluate_policy
  open SimulatedTrade (never order_send)
        ↓
  MetricsEngine + equity curve
        ↓
backtest_runs / backtest_trades / metrics / equity_curves
```

**Never executes. Never enables `EXECUTION_ENABLED`. Never calls `order_send()`.**

---

## Modules

### 1. Historical Replay Engine

`HistoricalReplayEngine` + `VirtualClock` + `ReplayController`

- Candle replay and tick replay  
- Deterministic virtual clock  
- Replay speed control  
- Pause / resume / step forward  

### 2. Simulation Engine

`BacktestEngine` replays Strategy Runtime (and Risk via strategy path) and optionally Execution Safety policy checks. Fills are **simulated only**.

### 3. Virtual Portfolio

Tracks equity, balance, floating P/L, realized P/L, margin, peak equity, max drawdown %.

### 4. Simulated Trades

Entries, exits, SL, TP, fees, spread, slippage assumptions. Exit reasons: stop_loss, take_profit, end_of_data, etc.

### 5. Metrics Engine

total return, CAGR, Sharpe, Sortino, Profit Factor, Expectancy, Win Rate, Average R, Max Drawdown, Recovery Factor.

### 6. Equity Curve

Per-bar equity, balance, and drawdown points persisted on the run (and dedicated SQL table).

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/backtests/run` | completed run + trades + metrics + equity curve |
| `GET` | `/api/v1/backtests` | list of runs for current user |
| `GET` | `/api/v1/backtests/{id}` | one run with simulated trades |

Request supplies historical `bars` (or `ticks`) — **no live MT5 market fetch required** for the run.

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712151000_backtest_engine.sql` | `backtest_runs`, `backtest_trades`, `backtest_metrics`, `backtest_equity_curves` |
| `20260712151100_backtest_engine_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No live execution records.**

---

## Key paths

| Layer | Path |
|-------|------|
| Enums | `app/domain/enums/backtest.py` |
| Entities | `app/domain/entities/backtest.py` |
| Events | `app/domain/events/backtest.py` |
| Replay | `app/application/services/historical_replay.py` |
| Metrics | `app/application/services/backtest_metrics.py` |
| Engine | `app/application/services/backtest_engine.py` |
| Use cases | `app/application/use_cases/backtest.py` |
| Router | `app/presentation/routers/backtest.py` |
| Persistence | `app/infrastructure/persistence/memory_backtest.py` |
| DI | `core/di/container.py` (`backtest_engine`, `backtest_uow_factory`) |

---

## Testing / CI

- Mock MT5 only; asserts `execution_enabled is False` and `order_send` disabled  
- **ruff** / **black** / **mypy** — green  
- **pytest** — **274 passed**, 2 skipped, ~80% coverage  

---

## Stop line

Backtesting Engine is complete.  
**Do not** enable execution.  
**Do not** implement AI.  
**Do not** place live trades.
