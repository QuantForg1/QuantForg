# Closed-trade strategy attribution gap — root cause

**Date:** 2026-11-04  
**Production:** commit `4cb42e5` · deploy `7b34d8bc` · mode LIVE  
**Severity:** P0 **monitoring / analytics** (does not explain entry losses; does not change Risk)

## Observed

| Source | Fact |
|---|---|
| Broker history | 5 closed XAUUSD trades, net −$1.78 |
| SOE orchestration monitor | All five strategies `closed_trades=0`, `wins=0`, `losses=0` |
| Strategy performance telemetry | `executed_signals=7`, `total_trades=0`, `tp_exits=0`, `sl_exits=0` |
| Lifecycle (executed) | Tickets `683675942`, `683682967` → `strategy_id=trend_continuation` |
| NOC `closed_trades` | 5 rows, `source=mt5_history_deals`, no `strategy_id` |

## Intended design

```
OMS fill
  → remember_fill_metadata(strategy_id, comment_hash, ticket…)
  → StrategyAttributionStore.bind_fill(ticket / position_id → strategy_id)
  → (MT5 comment is NOT source of truth; exits overwrite to [sl]/[tp])

PME local exit (state exited/closed)
  → merge_position_metadata(snapshot, live_meta, attribution_store.resolve)
  → if strategy_id: StrategyStatsBook.record_closed(...)
  → StrategyPerformanceTelemetry.observe_close(...)
```

Code refs:

- Bind: `institutional_ite_runtime.py` (~2792–2828)
- Store: `ai_scalping/strategies/attribution_store.py`
- Merge: `management/class_policy.py` `merge_position_metadata`
- Record: `institutional_ite_runtime.py` (~2097–2134) inside PME close branch

## Failure mode (verified)

Broker-side SL/TP removes the position from the MT5 book. QuantForg then runs position truth repair:

1. `mt5_position_truth._repair_internal_engine` → `PositionManagementEngine.drop_missing_tickets`
2. Stale tickets are `pop`’d from `_positions`
3. Log only: `Position Closed` / `reason=missing_from_mt5_book`
4. **No** `merge_position_metadata`, **no** `record_closed`, **no** `observe_close`

Therefore fill-time bindings never convert into closed SOE stats for the normal SL/TP path.

## Why comment / last-fill meta cannot rescue closes

- Exit deal comments are `[sl …]` / `[tp …]` — hash match to `ite:v1:…:hash` fails.
- `last_fill_metadata()` is last-fill only; concurrent/prior tickets need the ticket store.
- Ticket store is never consulted on the `missing_from_mt5_book` drop path.

## Deal vs position ticket (secondary)

Entry deals: `deal ticket` ≠ `position_id`; `order_ticket` on entry often equals `position_id` (e.g. deal `661318398`, position/order `683675942`). Bind prefers `order_ticket` then falls back to deal ticket. If a fill object only exposes deal ticket, resolve on close by position id would miss. Primary gap above still applies even when keys match.

## Recommended fix (owner approval required — frozen modules)

**Modules:** Position Recovery / MT5 position truth (`mt5_position_truth.py`), PME (`management/engine.py` `drop_missing_tickets`), optionally ITE runtime for shared close helper.

**Behavior:** When dropping a stale QuantForg ticket as missing from MT5:

1. Resolve `StrategyAttributionStore` by ticket/position id.
2. Load realized PnL from broker history deal for that position when available (do not invent).
3. Call the same closed-loop helpers as PME exit: `record_closed`, `observe_close`, attribution `note_partial_close(fully_closed=True)`.
4. Regression tests: bind → simulate missing_from_mt5_book → assert stats `closed_trades=1`.

**Must not:** bypass `OWNER_SL_RISK` / `OWNER_MIN_RR`, change strategy thresholds, weaken Risk, or place test orders.

## Status

**Owner-approved analytics repair implemented** on branch `fix/close-attribution-analytics`  
(see `CLOSE_ATTRIBUTION_REPAIR_REPORT.md`). Trading thresholds / order paths unchanged.
