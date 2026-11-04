# Close-attribution analytics repair — before/after

**Date:** 2026-11-04  
**Branch:** `fix/close-attribution-analytics`  
**Owner authorization:** analytics-only fix for `drop_missing_tickets` / `missing_from_mt5_book` → `record_closed` / `observe_close`  
**Base production commit (pre-change):** `4cb42e5`

## Before

| Check | Result |
|---|---|
| Broker closed trades | 5 (history deals) |
| SOE `closed_trades` | **0** all strategies |
| Telemetry `total_trades` / `tp_exits` / `sl_exits` | **0** |
| LIVE fills `683675942`, `683682967` | `strategy_id=trend_continuation` at execute; SL −2.00 / −1.55 |
| Path | PME/truth `drop_missing_tickets` logged `missing_from_mt5_book` and popped rows — **no** analytics hooks |

## Change (narrow)

| File | Role |
|---|---|
| `app/application/services/close_attribution.py` | **New** — broker exit evidence, idempotent ledger, record hooks, historical reconcile |
| `app/application/services/mt5_position_truth.py` | Reliable fetch gate; attribute before drop; pending + historical backfill |
| `app/application/services/institutional_ite_runtime.py` | PME local-exit path marks same ledger (no double-count) |
| `tests/unit/test_close_attribution.py` | SL/TP/outage/None snapshot/delayed history/dup/partial/missing strategy/historical |

**Unchanged:** order_send, SL/TP placement, Risk, OMS, strategy thresholds, owner policy, PME protective management actions.

### Safeguards

1. `list_positions` **exception** or **`None`** → `reliable=False`, **no PME drop**, **no analytics**, `apply_mt5_position_truth` no-op.  
2. Reliable empty book without exit deal → PME drop allowed; analytics **pending** until history confirms (no invented PnL).  
3. Analytics require paired broker exit deal (`entry_out`).  
4. Idempotent ledger keys `full:{position_id}` (+ exit deal).  
5. Strategy ID from attribution store / fill-lifecycle bindings only — never invented.  
6. Historical tickets `683675942` / `683682967` rebound from **fill evidence** (`trend_continuation`) then recorded from **broker deals**.

## After (unit / expected production)

| Check | Result |
|---|---|
| Regression suite `test_close_attribution.py` | **11 passed** |
| Historical reconcile net for two losers | **−3.55** (matches broker −2.00 + −1.55) |
| Duplicate reconcile | `status=duplicate`, losses stay 2 |
| Gateway timeout / None snapshot | Position remains managed; SOE unchanged |
| Production after deploy | Next reliable sync with history backfills the two tickets once; future SL/TP closes attribute automatically |

## Production deploy notes

1. Merge PR after CI green.  
2. Deploy Railway API — **do not** restart unnecessarily beyond normal deploy.  
3. Confirm LIVE remains Enabled / kill disarmed.  
4. Verify SOE monitor: `trend_continuation` `closed_trades` / losses reflect broker-confirmed exits (at least the two backfilled tickets once history is read).  
5. Confirm no new OMS submits from this change (analytics only).

## Acceptance mapping

| Criterion | Status |
|---|---|
| Confirmed broker exits reach strategy analytics | Implemented |
| Each close recorded exactly once | Ledger + tests |
| Original strategy attribution preserved | Store + fill bindings |
| Historical P&L agrees with broker | −3.55 vs deals |
| Temporary missing-ticket ≠ false close | Outage / None tests |
| MT5 execution / PME protect / policy unchanged | No order or Risk edits |
