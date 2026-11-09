# Multi-User MT5 — Phase 1a + 1B Status

**Branches:** `feat/multi-account-phase1a-registry` (PR #207), `feat/multi-user-mt5-worker-infra`  
**LIVE fan-out:** **DISABLED**

## Product rule

One user → one active MT5 account → one isolated worker runtime (when hosts exist).

## Phase 1a (registry)

| Item | Status |
| --- | --- |
| One account per user + global login uniqueness | Done |
| Worker assignment metadata table | Done |
| Effective risk + signal intent models | Done |
| Flags default OFF | Done |

## Phase 1B (worker infrastructure)

| Item | Status |
| --- | --- |
| Lifecycle / provisioner / capacity / supervisor | Done (control plane) |
| Windows agent interface + idle entrypoint | Done (deployable code) |
| Mock agent unit isolation tests | Done |
| Actual Windows hosts provisioned | **0** |
| Actual MT5 terminal sessions running | **0** |
| Concurrent demo authentications proven | **0** |

See `MULTI_USER_MT5_WORKER_INFRA.md` and `MT5_WORKER_INTEGRATION_TEST.md`.
