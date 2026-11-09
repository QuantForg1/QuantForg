# Multi-User MT5 Registry — Phase 1a Status

**Branch:** `feat/multi-account-phase1a-registry`  
**Baseline:** `main` @ `d92e17bc`  
**LIVE multi-user fan-out:** **DISABLED** (both env flags default `false`)

## Product rule (this phase)

```text
One QuantForg user  →  at most ONE non-revoked MT5 account
One MT5 account     →  at most ONE active worker *assignment* row
Many users          →  each may own one account (registry)
```

Do **not** build multiple MT5 accounts per user in this phase.

## What is implemented (registry only)

| Component | Status |
| --- | --- |
| Feature flags default OFF | Done |
| Global login uniqueness `(broker, server, login)` | Domain + memory repo + migration SQL |
| One active account per user | Domain + use case + memory repo + migration SQL |
| Worker assignment registry (metadata only) | Domain + migration SQL |
| Ownership verify-after-auth model | Domain (mocked auth in tests) |
| Effective risk strictest-of-three | Domain + unit tests |
| Signal / per-user execution intent models | Domain + unit tests |
| Honest capability statement | `REGISTRY_CAPABILITY_STATEMENT` |

## What is NOT implemented / NOT proven

| Claim | Reality |
| --- | --- |
| Provisioned isolated MT5 terminals | **0** |
| Concurrent authenticated MT5 sessions | **0** (singleton LIVE gateway remains) |
| Demo accounts executing simultaneously | **0** |
| Independent LIVE order submission / reconciliation | **Not proven** |
| Connect UX (broker/login/password/server → Verified) | **Not shipped** |
| Production migration applied | **No** |

Placeholder `execution_workers` rows are **assignment metadata**, not running workers.

## Existing LIVE Weltrade path

Unchanged. Owner singleton gateway remains the production execution path while flags stay off.

## Next phases (separate)

1. Isolated MT5 worker provisioning (one terminal session per user account).
2. Credential-based connect + verify UX inside QuantForg.
3. Central signal dispatcher → independent user workers.
4. Per-user risk evaluation, OMS, reconciliation.
5. Concurrent demo proof → controlled LIVE enablement (explicit owner approval).
