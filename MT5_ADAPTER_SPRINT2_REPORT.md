# MT5 Adapter Sprint 2 Report — Market Data Layer

**Status:** Complete  
**Scope:** MetaTrader 5 **market data only** (symbols, ticks, candles)  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Order execution / `order_send()`  
- Positions  
- Strategy execution  
- AI  
- Tick persistence / streaming subscriptions  

MT5 Adapter Sprint 1, Broker Foundation, Auth, User Platform, and Supabase are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Symbol management (`list_symbols`, `symbol_info`, `symbol_select`) | Yes |
| Tick data (`latest_tick` + bid/ask/spread/timestamp) | Yes |
| Candles (`copy_rates_from` / `range` / `from_pos`) | Yes |
| Timeframes M1…MN1 | Yes |
| `MT5MarketDataService` | Yes |
| Events: `TickReceived`, `CandleReceived`, `MarketDataUpdated` | Yes |
| REST market-data routes | Yes |
| Optional symbol metadata cache (no tick storage) | Yes |
| MockMT5Client tests / CI green | Yes |

---

## Architecture

```
GET /api/v1/mt5/symbols|ticks|candles
        ↓
MT5Service / use cases
        ↓
MT5MarketDataService  →  events (TickReceived, CandleReceived, MarketDataUpdated)
        ↓
MT5Adapter  →  MockMT5Client (default)
```

Clean Architecture preserved. No MetaTrader5 package in domain/application.

---

## Domain

| Type | Module |
|------|--------|
| `MT5Tick` | `app/domain/entities/mt5_market.py` |
| `MT5Rate` | same |
| `MT5SymbolInfo` | same |
| `Timeframe` | existing `app/domain/market_data/timeframe.py` (M1–MN1) |
| `CandleReceived`, `MarketDataUpdated` | `app/domain/events/mt5.py` |
| `TickReceived` | existing `app/domain/events/market.py` (re-exported) |

---

## Client / Adapter API

Extended on `MT5ClientPort` + `MockMT5Client` + `MT5Adapter`:

| Method | Purpose |
|--------|---------|
| `list_symbols()` | Full symbol catalogue |
| `symbol_info(symbol)` | Digits, point, bid/ask, selected |
| `symbol_select(symbol, enable=)` | Market Watch selection |
| `latest_tick(symbol)` | bid, ask, spread, timestamp |
| `copy_rates_from(...)` | Bars from datetime + count |
| `copy_rates_range(...)` | Bars in date range |
| `copy_rates_from_pos(...)` | Bars from position |

Supported timeframes: **M1, M5, M15, M30, H1, H4, D1, W1, MN1**.

Orders/positions remain `NotImplementedError`.

---

## Market Data Service

`app/application/services/mt5_market_data.py`

- `historical_candles(...)`
- `latest_candle(...)`
- `latest_tick(...)`
- Emits domain events into an in-process buffer (no bus required this sprint)

---

## API

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/v1/mt5/symbols` | List (Sprint 1, enriched) |
| `GET` | `/api/v1/mt5/symbols/{symbol}` | Symbol info |
| `GET` | `/api/v1/mt5/ticks/{symbol}` | Latest tick |
| `GET` | `/api/v1/mt5/candles/{symbol}` | Query: `timeframe`, `count`, `start_pos`, `date_from`, `date_to` |

Requires an active MT5 connection (Sprint 1 connect).

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712144000_mt5_market_data.sql` | `mt5_symbol_cache` (metadata only) |
| `20260712144100_mt5_market_data_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**Ticks are not persisted.** Cache is optional symbol metadata only.

---

## Testing

`tests/unit/test_mt5_market_data.py` — MockMT5Client only (no real terminal).

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → green (coverage ≥ 60%)
```

---

## Stop line

Sprint 2 ends at the **Market Data Layer**.

Do **not** implement:

- Orders  
- Positions  
- `order_send()`  
- Strategy execution  
- AI  
