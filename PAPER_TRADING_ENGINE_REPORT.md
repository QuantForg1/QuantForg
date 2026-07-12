# Paper Trading Engine Report

**Status:** Complete  
**Scope:** Live market data + **simulated** fills only  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Enabling `EXECUTION_ENABLED` (remains **false**)  
- Calling `order_send()`  
- Live broker order placement  
- AI / ML  

Backtesting Engine, Strategy Runtime, Risk Engine, Execution Gateway, MT5 Adapter, Broker Foundation, Auth, User Platform, Supabase, and CI are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Virtual Broker (accept / fill / reject + spread / slippage / commission) | Yes |
| Live Market Listener (MT5 ticks, candles, symbol updates) | Yes |
| Paper Portfolio (balance, equity, margin, floating/realized P/L, drawdown) | Yes |
| Paper Orders (market / limit / stop) | Yes |
| Paper Positions (opened / partially_closed / closed) | Yes |
| Events: Opened / Closed / Filled / Rejected | Yes |
| `POST /api/v1/paper/orders` | Yes |
| `GET /api/v1/paper/positions` | Yes |
| `GET /api/v1/paper/history` | Yes |
| `GET /api/v1/paper/performance` | Yes |
| Persist trades, orders, positions, performance + RLS | Yes |
| Tests + CI green | Yes |

---

## Architecture

```
POST /api/v1/paper/orders
        ↓
PlacePaperOrderUseCase
        ↓
PaperTradingEngine.place_order
  PaperMarketListener ← MT5MarketDataService (Mock MT5 ticks/candles/symbols)
        ↓
  VirtualBroker.submit
    accept | reject
    simulate fill (spread + slippage + commission)
        ↓
  PaperPosition + PaperPortfolio mark-to-market
        ↓
paper_orders / paper_positions / paper_trades / paper_performance
```

**Uses live (Mock) market data. Never calls `order_send()`. Never enables `EXECUTION_ENABLED`.**

---

## Modules

### 1. Virtual Broker

`VirtualBroker` simulates order acceptance, fills, slippage, commissions, and spread. Margin checks reject oversized exposure. Limit/stop orders stay `accepted` until price triggers.

### 2. Live Market Listener

`PaperMarketListener` consumes MT5:

- latest tick  
- latest candle  
- symbol updates / list  

Read-only — no execution path.

### 3. Paper Portfolio

Tracks balance, equity, floating P/L, realized P/L, margin, free margin, peak equity, max drawdown %.

### 4. Paper Orders

`market` | `limit` | `stop` — simulation only. Optional `reduce_position_id` closes/reduces an open position.

### 5. Paper Positions

Lifecycle: `opened` → `partially_closed` → `closed`. SL/TP checked against live ticks on refresh.

### 6. Events

| Event | When |
|-------|------|
| `PaperTradeOpened` | Position opened from fill |
| `PaperTradeClosed` | Position (or partial) closed |
| `PaperOrderFilled` | Virtual broker fill |
| `PaperOrderRejected` | Virtual broker reject |

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/paper/orders` | order + optional position/trade + portfolio + quote |
| `GET` | `/api/v1/paper/positions` | open positions (MTM) + portfolio |
| `GET` | `/api/v1/paper/history` | orders, trades, positions |
| `GET` | `/api/v1/paper/performance` | performance metrics + portfolio |

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712152000_paper_trading.sql` | portfolios, orders, positions, trades, performance |
| `20260712152100_paper_trading_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No live execution records.**

---

## Key paths

| Layer | Path |
|-------|------|
| Enums | `app/domain/enums/paper.py` |
| Entities | `app/domain/entities/paper.py` |
| Events | `app/domain/events/paper.py` |
| Market listener | `app/application/services/paper_market_listener.py` |
| Virtual broker | `app/application/services/virtual_broker.py` |
| Engine | `app/application/services/paper_trading.py` |
| Use cases | `app/application/use_cases/paper.py` |
| Router | `app/presentation/routers/paper.py` |
| Persistence | `app/infrastructure/persistence/memory_paper.py` |
| DI | `core/di/container.py` (`paper_trading_engine`, `paper_uow_factory`) |

---

## Testing / CI

- Mock MT5 for live quotes  
- Asserts `execution_enabled is False` and `order_send` disabled  
- **ruff** / **black** / **mypy** — green  
- **pytest** — **279 passed**, 2 skipped, ~80% coverage  

---

## Stop line

Paper Trading Engine is complete.  
**Do not** enable live execution.  
**Do not** implement AI.  
**Do not** call `order_send()`.
