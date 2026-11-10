# Phase 6 implementation checklist

## Done in this foundation

- [x] Architecture document
- [x] Dry-run dispatch planner (no OMS / order_send)
- [x] Idempotency ledger (in-memory)
- [x] Eligibility integration per target
- [x] Foreign-actor denial path
- [x] Unit tests proving delivery suppression
- [x] Feature flags remain default OFF

## Remaining before demo execution

- [ ] Durable Postgres dispatch queue + migrations
- [ ] Worker delivery protocol + ACK
- [ ] Isolated Windows hosts with verified heartbeats **and** broker auth evidence
- [ ] Staging env + disposable test identities
- [ ] Owner approval to enable `MULTI_ACCOUNT_DISPATCH_ENABLED` on staging only

## Remaining before LIVE fan-out

- [ ] Owner-signed LIVE submit enablement
- [ ] Trading-core + OMS regression under multi-account load
- [ ] Per-user breach isolation proven in staging
- [ ] Monitoring / audit dashboards
- [ ] Explicit decision **not** to use Weltrade singleton as shared multi-user terminal
