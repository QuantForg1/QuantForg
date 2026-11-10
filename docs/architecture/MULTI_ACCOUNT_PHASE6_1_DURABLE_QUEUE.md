# Multi-account Phase 6.1 — Durable dispatch queue

**Status:** Durable queue + worker claim/ACK foundation. LIVE fan-out **DISABLED**.  
**Depends on:** Phase 6 dry-run planner, Phase 5.1 eligibility, Phase 1a `account_execution_intents`.

## What shipped

| Piece | Path |
|---|---|
| Lease / delivery migration | `supabase/migrations/20261110210000_dispatch_queue_lease.sql` |
| RLS for delivery events | `20261110210100_dispatch_queue_lease_rls.sql` |
| Delivery vocabulary | `app/domain/multi_account/dispatch_queue.py` |
| Durable queue service | `app/application/services/multi_account_dispatch_queue.py` |
| Postgres mirror | `app/infrastructure/persistence/postgres_signal_dispatch.py` |
| Worker APIs | `POST /mt5-workers/dispatch/{claim,ack,fail,recover}` |
| Tests | `tests/unit/test_phase61_durable_dispatch_queue.py` |

## State mapping

| Operator label | `AccountExecutionState` | `DeliveryStatus` |
|---|---|---|
| PENDING | `received` | `none` |
| ELIGIBILITY_CHECK | `eligibility_pending` | `none` |
| BLOCKED | `blocked` | `none` |
| QUEUED | `queued` | `pending` |
| DELIVERED | `queued` | `delivered` |
| ACKNOWLEDGED | `queued` | `acked` |
| EXECUTION_REPORTED | `acknowledged` | `acked` (future LIVE) |
| FAILED | retry → `pending` or `dead_letter` | `failed` / `dead_letter` |
| EXPIRED | lease release → `pending` | `expired` |
| CANCELLED | `cancelled` | `cancelled` |

### Allowed delivery transitions

`none → pending|cancelled`  
`pending → claimed|cancelled|expired|dead_letter`  
`claimed → delivered|failed|expired|pending|cancelled`  
`delivered → acked|failed|expired`  
`failed → pending|dead_letter|cancelled`  
`expired → pending|dead_letter|cancelled`  
`acked`, `cancelled`, `dead_letter` are terminal for delivery.

### Retry / lease

- Default lease: 60s  
- Max attempts: 5 (exponential backoff, cap 300s)  
- Restart recovery: `recover_after_restart()` releases `claimed` → `pending`  
- Concurrent claim: exclusive under process lock (PG path uses unique idempotency + lease columns)

## Safety

- `MULTI_ACCOUNT_DISPATCH_ENABLED` / `LIVE_SUBMIT` remain default **false**
- Queue forces `live_submit_allowed=False` and `delivery_suppressed=True`
- No OMS / `order_send` imports or calls
- Payload scrub strips password/token/sealed credentials
- Claim is scoped to `(user_id, broker_account_id)` — no cross-user claim
- User kill switch and account revoke cancel/block that user only

## Demo / LIVE

| Capability | Status |
|---|---|
| Durable enqueue / claim / ACK (in-process) | Implemented |
| Postgres mirror when migration applied | Implemented (falls back if not ready) |
| Real Windows MT5 demo auth | **BLOCKED** — credentials / hosts not provisioned |
| Demo order execution | **BLOCKED** — not authorized; flags OFF |
| LIVE multi-account submit | **FORBIDDEN** without separate Owner authorization |
