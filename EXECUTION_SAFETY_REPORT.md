# Execution Safety Layer Report

**Status:** Complete  
**Scope:** Production-grade **pre-execution safety pipeline** (decisions only)  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Live trading / `order_send()`  
- Positions  
- Strategy execution  
- AI  

Broker Foundation, MT5 Sprints 1–3, Auth, User Platform, and Supabase are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| `ExecutionPolicy` (spread, slippage, hours, whitelists, leverage, lots) | Yes |
| `RiskPreCheck` (margin, account, connection, market, volume, stops, freeze) | Yes |
| Duplicate / replay / rapid-submit protection | Yes |
| Idempotency via `request_id` | Yes |
| Decisions: **ALLOW** / **REJECT** / **RETRY** only | Yes |
| Events: `ExecutionApproved`, `ExecutionRejected`, `ExecutionRetryRequested` | Yes |
| `POST /api/v1/execution/check` | Yes |
| Decision history + RLS (no credentials, no live orders) | Yes |
| MockMT5 tests / CI green | Yes |

---

## Architecture

```
POST /api/v1/execution/check
        ↓
CheckExecutionSafetyUseCase
        ↓
ExecutionSafetyService
  policy → risk pre-check → duplicate/idempotency → ALLOW|REJECT|RETRY
        ↓
MT5Adapter / MockMT5Client (check/calc only — never order_send)
        ↓
execution_decisions (history only)
```

Clean Architecture preserved. **Never calls `order_send()`.**

---

## Modules

### 1. ExecutionPolicy

`app/domain/entities/execution_safety.py`

| Constraint | Field |
|------------|--------|
| Max spread | `max_spread` |
| Max slippage | `max_slippage` |
| Trading hours | `trading_hours_start` / `trading_hours_end` |
| Symbol whitelist | `symbol_whitelist` |
| Account whitelist | `account_whitelist` |
| Leverage limit | `max_leverage` |
| Max / min lot | `max_lot` / `min_lot` |

### 2. RiskPreCheck

Validates: free margin, account status, broker connection, market open, symbol tradable, volume limits, stop distance, freeze level.

### 3–4. Duplicate protection & idempotency

- Fingerprint over intent fields + user  
- Same fingerprint in window → **RETRY**  
- Rapid repeats → **REJECT**  
- Same `request_id` → safe replay of prior decision (`idempotent_replay=true`)

### 5. Execution decision

Enum `ExecutionDecision`: `allow` | `reject` | `retry` — never execute.

### 6. Events

| Event | `event_type` |
|-------|----------------|
| `ExecutionApproved` | `execution.approved` |
| `ExecutionRejected` | `execution.rejected` |
| `ExecutionRetryRequested` | `execution.retry_requested` |

### 7. API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/execution/check` | decision, rejection reasons, warnings, calculated risk, checks |

Requires an active MT5 connection. Body must include `request_id`.

### 8. Database

| Migration | Purpose |
|-----------|---------|
| `20260712146000_execution_safety.sql` | `execution_decisions` |
| `20260712146100_execution_safety_rls.sql` | Owner RLS (SELECT/INSERT own) |
| Matching `down/*.down.sql` | Reversible |

Unique index on `(user_id, request_id)` for non-replay rows.  
**No credentials. No live orders.**

---

## Testing

`tests/unit/test_execution_safety.py` — MockMT5Client only:

- Policy validation  
- Risk rejection (volume)  
- Duplicate → RETRY / rapid → REJECT  
- Idempotent `request_id` replay  
- `order_send` still raises `NotImplementedError`

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 242 passed, 2 skipped (~79% coverage)
```

---

## Stop line

This layer ends at the **Execution Safety Pipeline**.

Do **not** implement:

- `order_send()`  
- Live trading  
- Positions  
- Strategy execution  
- AI  
