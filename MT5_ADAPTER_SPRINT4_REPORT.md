# MT5 Adapter Sprint 4 Report — Execution Gateway

**Status:** Complete  
**Scope:** Execution **infrastructure only** — live send gated by feature flag  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Strategy runtime  
- AI  
- Enabling live execution by default  

All prior sprints (Broker Foundation, MT5 1–3, Execution Safety, Portfolio Engine, Auth, User Platform, Supabase, CI) are preserved.

---

## Feature flag

| Setting | Env | Default |
|---------|-----|---------|
| `execution_enabled` | `EXECUTION_ENABLED` | **`false`** |

When `false`:

- `MT5Adapter.order_send()` **never** calls the client  
- Returns deterministic disabled retcode `90001`  
- `POST /api/v1/execution/submit` → **HTTP 403** (`execution_disabled`)

---

## Summary

| Feature | Delivered |
|---------|-----------|
| `ExecutionGateway.prepare()` / `submit()` / `cancel()` | Yes |
| Gated `order_send()` (flag only) | Yes |
| Retcode → domain `ExecutionResult` mapping | Yes |
| Events: Requested / Submitted / Failed / Disabled | Yes |
| `POST /api/v1/execution/submit` (403 when disabled) | Yes |
| Persist attempts (requests, results, retcodes, timestamps) | Yes |
| RLS + reversible migrations | Yes |
| MockMT5 `order_send` + CI green | Yes |

---

## Architecture

```
POST /api/v1/execution/submit
        ↓
SubmitExecutionUseCase  (idempotency via request_id)
        ↓
ExecutionGateway.prepare → submit
        ↓
if EXECUTION_ENABLED=false → ExecutionDisabled + HTTP 403
if true → MT5Adapter.order_send → MockMT5Client.order_send
        ↓
map retcode → ExecutionResult (never raw MT5 structs)
        ↓
execution_attempts (history only)
```

`/execution/check` (safety layer) is unchanged and never sends.

---

## ExecutionGateway

`app/application/services/execution_gateway.py`

| Method | Behavior |
|--------|----------|
| `prepare(intent)` | Build `TradeRequest` (no send) |
| `submit(intent, …)` | Prepare + gated send + map result |
| `cancel(ticket, …)` | Gated pending-order cancel |

---

## Result mapping

Domain `ExecutionOutcome`: `success` | `failed` | `disabled` | `retry` | `cancelled` | `prepared`

Notable retcodes: `10009` success, `10004`/`10012`/`10021` retryable, `90001` QuantForg disabled.

Raw `MT5OrderSendResult` stays inside the adapter; API/DTO expose `ExecutionResult` / `ExecutionAttempt` only.

---

## Events

| Event | `event_type` |
|-------|----------------|
| `ExecutionRequested` | `execution.requested` |
| `ExecutionSubmitted` | `execution.submitted` |
| `ExecutionFailed` | `execution.failed` |
| `ExecutionDisabled` | `execution.disabled` |

(Safety events `Approved` / `Rejected` / `RetryRequested` unchanged.)

---

## API

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/api/v1/execution/check` | Safety only (unchanged) |
| `POST` | `/api/v1/execution/submit` | Gateway; **403** if disabled |

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712148000_execution_gateway.sql` | `execution_attempts` |
| `20260712148100_execution_gateway_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

Stores: request_id, outcome, retcode, tickets, snapshots, timestamps.  
**No credentials.**

---

## Testing

`tests/unit/test_execution_gateway.py` — MockMT5Client:

- Disabled mode (no client send)  
- Success / failure / retry mapping  
- Cancel  
- Idempotent `request_id`  
- Use case → `AuthorizationError` (HTTP 403)

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 254 passed, 2 skipped (~79% coverage)
```

---

## Stop line

Sprint 4 ends at the **Execution Gateway** (flag-gated infrastructure).

Do **not**:

- Build strategy runtime  
- Build AI  
- Enable live execution by default (`EXECUTION_ENABLED` remains `false`)  
