# Phase 6 / 6.1 implementation checklist

## Done — Phase 6 foundation

- [x] Architecture document
- [x] Dry-run dispatch planner (no OMS / order_send)
- [x] Idempotency ledger (in-memory)
- [x] Eligibility integration per target
- [x] Foreign-actor denial path
- [x] Unit tests proving delivery suppression
- [x] Feature flags remain default OFF

## Done — Phase 6.1 durable queue

- [x] Postgres lease / delivery_status migration + RLS
- [x] Durable queue service (enqueue, claim, ACK, fail, recover)
- [x] Idempotent enqueue + concurrent claim tests
- [x] Restart recovery + stale lease expiry
- [x] Kill switch / revoked account isolation
- [x] Worker token claim/ACK/fail/recover routes
- [x] Secret scrubbing in payloads
- [x] Phase 6.1 documentation

## Remaining before demo execution

- [ ] Apply lease migration on Production/Staging Supabase (Owner)
- [ ] Isolated Windows hosts with verified heartbeats **and** broker auth evidence
- [ ] Staging env + disposable test identities + demo credentials
- [ ] Owner approval to enable `MULTI_ACCOUNT_DISPATCH_ENABLED` on staging only
- [ ] Postgres `SKIP LOCKED` claim under concurrent workers (staging soak)

## Remaining before LIVE fan-out

- [ ] Owner-signed LIVE submit enablement
- [ ] Trading-core + OMS regression under multi-account load
- [ ] Per-user breach isolation proven in staging
- [ ] Monitoring / audit dashboards (UI)
- [ ] Explicit decision **not** to use Weltrade singleton as shared multi-user terminal
