# MT5 Adapter Sprint 3 Report — Order Validation Layer

**Status:** Complete  
**Scope:** MetaTrader 5 **order preparation and validation only** (no execution)  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Live trading / `order_send()`  
- Positions  
- Strategy execution  
- AI  

MT5 Adapter Sprint 1–2, Broker Foundation, Auth, User Platform, and Supabase are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Domain: `TradeRequest`, `TradeValidation`, `OrderIntent`, `OrderConstraints` | Yes |
| VOs: `LotSize`, `StopLoss`, `TakeProfit`, `Slippage`, `MagicNumber` | Yes |
| `MT5OrderValidationService` (build + validate pipeline) | Yes |
| MT5: `order_check`, `order_calc_margin`, `order_calc_profit` | Yes |
| `order_send()` blocked (`NotImplementedError`) | Yes |
| REST validate / calculate | Yes |
| Validation history + RLS (no credentials) | Yes |
| MockMT5Client tests / CI green | Yes |

---

## Architecture

```
POST /api/v1/mt5/order/validate|calculate
        ↓
    MT5Service / use cases
        ↓
MT5OrderValidationService
  build_order_request → validate_* → order_check / calc_margin / calc_profit
        ↓
MT5Adapter  →  MockMT5Client (default)
        ↓
mt5_order_validations (history only)
```

Clean Architecture preserved. No MetaTrader5 package in domain/application.  
**Never calls `order_send()`.**

---

## Domain

| Type | Module |
|------|--------|
| `OrderConstraints` | `app/domain/entities/mt5_order.py` |
| `OrderIntent` | same |
| `TradeRequest` | same |
| `TradeValidation` | same |
| `LotSize`, `StopLoss`, `TakeProfit`, `Slippage`, `MagicNumber` | `app/domain/value_objects/mt5_order.py` |
| Check/calc result types + retcodes | `app/domain/interfaces/mt5_order.py` |

---

## Validation Service

`app/application/services/mt5_order_validation.py`

| Method | Purpose |
|--------|---------|
| `build_order_request()` | Map intent → `TradeRequest` |
| `validate_symbol()` | Symbol known / tradeable |
| `validate_volume()` | Min/max/step |
| `validate_stops()` | SL/TP vs side and stops level |
| `validate_margin()` | Free margin vs required |
| `validate_market_state()` | Trade allowed / market open |
| `validate_order()` | Full pipeline + broker `order_check` |

---

## Client / Adapter API

Extended on `MT5ClientPort` + `MockMT5Client` + `MT5Adapter`:

| Method | Purpose |
|--------|---------|
| `order_check(request)` | Pre-trade check (retcode, margin, comment) |
| `order_calc_margin(request)` | Expected margin |
| `order_calc_profit(request)` | Estimated profit |
| `order_send(request)` | **Raises `NotImplementedError`** |

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/mt5/order/validate` | validation result, margin, profit, retcode, messages, checks |
| `POST` | `/api/v1/mt5/order/calculate` | expected margin, estimated profit, retcode |

Requires an active MT5 connection (Sprint 1). Persists validation history on validate.

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712145000_mt5_order_validation.sql` | `mt5_order_validations` history table |
| `20260712145100_mt5_order_validation_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**Credentials are never stored.** Live orders are never stored. History only.

---

## Testing

`tests/unit/test_mt5_order_validation.py` — MockMT5Client only:

- `order_check` / `order_calc_margin` / `order_calc_profit` mocked  
- `order_send` asserted to raise  
- Validation pipeline (valid + invalid volume/stops)

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 234 passed, 2 skipped (~79% coverage)
```

---

## Stop line

Sprint 3 ends at the **Order Validation Layer**.

Do **not** implement:

- `order_send()`  
- Live trading  
- Positions  
- Strategy execution  
- AI  
