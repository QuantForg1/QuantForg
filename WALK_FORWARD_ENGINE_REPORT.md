# Walk-Forward Validation Engine Report

**Status:** Complete  
**Scope:** Deterministic IS/OOS validation before Paper Trading promotion  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Enabling `EXECUTION_ENABLED` (remains **false**)  
- Calling `order_send()`  
- AI / ML optimization  
- Live trade placement  
- Paper trading promotion execution (decision only)

Backtesting, Paper Trading, Strategy Runtime, Risk Engine, Execution Gateway, Broker Foundation, MT5 Adapter, Auth, User Platform, Supabase, and CI are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Rolling IS / OOS windows (configurable, rolling + anchored) | Yes |
| Validation: backtest IS → validate OOS → aggregate OOS | Yes |
| Deterministic IS parameter selection grid (not AI) | Yes |
| Robustness: parameter stability, consistency, overfitting, robustness, regime | Yes |
| Promotion: **PROMOTE_TO_PAPER** / **NEEDS_REWORK** / **REJECT** | Yes |
| Reports: IS metrics, OOS metrics, combined equity, robustness summary | Yes |
| `POST /api/v1/walkforward/run` | Yes |
| `GET /api/v1/walkforward/results` | Yes |
| `GET /api/v1/walkforward/{id}` | Yes |
| Persist runs, OOS metrics, robustness + RLS | Yes |
| Tests + CI green | Yes |

---

## Architecture

```
POST /api/v1/walkforward/run
        ↓
RunWalkForwardUseCase
        ↓
WalkForwardEngine
  RollingWindowScheduler → IS/OOS folds
        ↓ per fold
  BacktestEngine on IS (optional param grid pick)
  BacktestEngine on OOS (selected params)
        ↓
  aggregate OOS metrics only
  RobustnessEngine → scores
  promotion rules → PROMOTE_TO_PAPER | NEEDS_REWORK | REJECT
        ↓
walkforward_runs / oos_metrics / robustness_reports
```

**Never executes. Never enables `EXECUTION_ENABLED`. Never calls `order_send()`.**

Pipeline position:

```
Backtesting → Walk-Forward Validation → Paper Trading (if PROMOTE_TO_PAPER)
```

---

## Modules

### 1. Rolling Windows

`RollingWindowScheduler` supports:

- in-sample / out-of-sample sizes  
- step size  
- rolling or anchored schedules  

### 2. Validation Engine

`WalkForwardEngine` runs BacktestEngine on each IS segment, optionally selects the best deterministic param set from a fixed grid, then validates on OOS. Promotion uses **aggregated OOS metrics** (IS is diagnostic only).

### 3. Robustness Metrics

| Metric | Meaning |
|--------|---------|
| parameter_stability | Consistency of selected params across folds (0–100) |
| consistency_score | % of OOS folds with positive return |
| overfitting_score | IS vs OOS return gap (higher = more overfit) |
| robustness_score | Weighted blend (OOS-focused) |
| regime_stability | Inverse of OOS return dispersion |

### 4. Promotion Rules

| Decision | Typical condition |
|----------|-------------------|
| `promote_to_paper` | Robustness ≥ 60, overfitting ≤ 40, consistency ≥ 50, avg OOS > 0 |
| `reject` | Robustness < 30 or overfitting ≥ 70 or consistency ≤ 20 |
| `needs_rework` | Everything else |

### 5. Reports

Each run includes IS aggregate, OOS aggregate, combined OOS equity curve, fold details, and robustness summary.

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/walkforward/run` | full validation run + promotion |
| `GET` | `/api/v1/walkforward/results` | list of runs |
| `GET` | `/api/v1/walkforward/{id}` | one run with report |

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712153000_walkforward.sql` | runs, oos_metrics, robustness_reports |
| `20260712153100_walkforward_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No live execution records.**

---

## Key paths

| Layer | Path |
|-------|------|
| Enums | `app/domain/enums/walkforward.py` |
| Entities | `app/domain/entities/walkforward.py` |
| Events | `app/domain/events/walkforward.py` |
| Windows | `app/application/services/rolling_windows.py` |
| Robustness | `app/application/services/walkforward_robustness.py` |
| Engine | `app/application/services/walkforward_engine.py` |
| Use cases | `app/application/use_cases/walkforward.py` |
| Router | `app/presentation/routers/walkforward.py` |
| Persistence | `app/infrastructure/persistence/memory_walkforward.py` |
| DI | `core/di/container.py` (`walkforward_engine`, `walkforward_uow_factory`) |

---

## Testing / CI

- Mock MT5 only; asserts `execution_enabled is False` and `order_send` disabled  
- **ruff** / **black** / **mypy** — green  
- **pytest** — **282 passed**, 2 skipped, ~80% coverage  

---

## Stop line

Walk-Forward Validation Engine is complete.  
**Do not** enable execution.  
**Do not** implement AI.  
**Do not** place live trades.
