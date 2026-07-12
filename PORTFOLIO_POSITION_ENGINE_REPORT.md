# Portfolio & Position Engine Report

**Status:** Complete  
**Scope:** Read-only MT5 portfolio synchronization (positions, pending orders, history, account)  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Live trading / `order_send()`  
- Strategy runtime  
- AI  
- Changes to Execution Safety Layer  

Broker Foundation, MT5 Sprints 1–3, Execution Safety, Auth, User Platform, and Supabase are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Position engine: `list_positions`, `position_by_ticket`, `position_by_symbol` | Yes |
| Pending orders: `list_orders`, `order_by_ticket` | Yes |
| Trade history: `history_orders`, `history_deals` | Yes |
| Account snapshot (balance, equity, margin, free margin, margin level, profit, leverage) | Yes |
| `PortfolioSyncService` (read-only sync) | Yes |
| Events: PortfolioSynchronized, PositionOpened/ClosedDetected, PendingOrderDetected, AccountUpdated | Yes |
| REST: `/portfolio`, `/positions`, `/orders`, `/history` | Yes |
| Snapshots + history cache + RLS | Yes |
| MockMT5 tests / CI green | Yes |

---

## Architecture

```
GET /api/v1/portfolio|positions|orders|history
        ↓
Portfolio use cases
        ↓
PortfolioSyncService  →  events (opened/closed/pending/account/synced)
        ↓
MT5Adapter  →  MockMT5Client (read-only)
        ↓
portfolio_syncs / portfolio_history_cache
```

Clean Architecture preserved. **Never calls `order_send()`.**  
Execution Safety Layer untouched.

---

## Domain

| Type | Module |
|------|--------|
| `MT5Position` | `app/domain/entities/mt5_portfolio.py` |
| `MT5PendingOrder` | same |
| `MT5HistoryOrder` | same |
| `MT5Deal` | same |
| `AccountSnapshot` | same |
| `PortfolioState` / `PortfolioSyncRecord` | same |

`MT5AccountInfo` extended with margin / free_margin / margin_level / profit (defaults keep existing callers valid).

---

## Client / Adapter API

| Method | Purpose |
|--------|---------|
| `list_positions()` | Open positions |
| `position_by_ticket(ticket)` | Single position |
| `position_by_symbol(symbol)` | Positions for symbol |
| `list_orders()` | Pending orders |
| `order_by_ticket(ticket)` | Single pending order |
| `history_orders(...)` | Historical orders |
| `history_deals(...)` | Historical deals |
| `account_snapshot()` | Equity/margin snapshot |

`BrokerAdapterPort.get_positions` / `get_orders` implemented (read-only).  
Capabilities now include `POSITIONS` and `ORDERS` (read sync, not execution).  
`order_send` remains `NotImplementedError`.

---

## PortfolioSyncService

`app/application/services/portfolio_sync.py`

- Synchronize positions, pending orders, account, history  
- Detect opened/closed positions and new pending orders vs prior sync  
- Emit domain events into an in-process buffer  
- Persist sync snapshot via use case (history only)

---

## API

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/v1/portfolio` | Full sync + snapshot |
| `GET` | `/api/v1/positions` | Optional `?symbol=` |
| `GET` | `/api/v1/positions/{ticket}` | By ticket |
| `GET` | `/api/v1/orders` | Pending |
| `GET` | `/api/v1/orders/{ticket}` | By ticket |
| `GET` | `/api/v1/history` | Optional `date_from` / `date_to` |

Requires an active MT5 connection.

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712147000_portfolio_engine.sql` | `portfolio_syncs`, `portfolio_history_cache` |
| `20260712147100_portfolio_engine_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No execution records.** Snapshots and history cache only.

---

## Testing

`tests/unit/test_portfolio_engine.py` — MockMT5Client only.

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 245 passed, 2 skipped (~79% coverage)
```

---

## Stop line

This phase ends at the **Portfolio & Position Engine** (read-only sync).

Do **not** implement:

- `order_send()` / live execution  
- Strategy runtime  
- AI  
- Modifications to Execution Safety  
