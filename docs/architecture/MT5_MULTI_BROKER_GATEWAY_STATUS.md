# MT5 Multi-Broker Gateway — implementation status

**Date:** 2026-11-09  
**Scope:** Six-broker MT5 connectivity on the **existing Windows host** (no new VPS)

## Infrastructure decision

| Option | Verdict |
|---|---|
| New Windows VPS | **Not provisioned** (explicit product decision) |
| Existing Windows host | **Retained** — portable slots + capacity soft-cap |
| Railway Linux | Cannot run `terminal64.exe` |
| Weltrade LIVE Program Files terminal | **Protected** — workers refuse this path |

### Measured capacity (existing host)

| Metric | Observed |
|---|---|
| CPU logical | 4 |
| RAM | ~8 GB (free often ~2 GB with LIVE terminal) |
| Disk free | ~3–4 GB (tight) |
| Prepared portable slots | `demo-a`, `demo-b` (`demo-c` optional) |
| Soft concurrent portable cap | **2** (`QF_MT5_MAX_CONCURRENT_PORTABLES`) |
| Queue | FIFO when capacity exhausted |

## Production-verified

| Capability | Status |
|---|---|
| Weltrade Demo + Live | **Operational** |
| Credential encryption | AES-256-GCM / existing secret store |
| Robot / OMS / kill switches | **Unchanged** — LIVE multi-account submit **off** |
| Evidence gate | `connectable=true` only after real Windows verify |

## Six-broker verification matrix

| Broker | Demo | Live | Market data | Recovery | Connectable |
|---|---|---|---|---|---|
| Exness | **BLOCKED** (no approved creds) | **BLOCKED** | BLOCKED | BLOCKED | No |
| HFM | **BLOCKED** | **BLOCKED** | BLOCKED | BLOCKED | No |
| IC Markets | **BLOCKED** | **BLOCKED** | BLOCKED | BLOCKED | No |
| Pepperstone | **BLOCKED** | **BLOCKED** | BLOCKED | BLOCKED | No |
| FP Markets | **BLOCKED** | **BLOCKED** | BLOCKED | BLOCKED | No |
| XM | **BLOCKED** | **BLOCKED** | BLOCKED | BLOCKED | No |

BLOCKED = approved credentials / verified session missing — **not** simulated success.

Documented search hints exist for admin/discovery only. Verified selectable servers remain empty until Windows login returns `account_info.server`.

## Operator verify (when credentials are approved)

```powershell
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker exness -Slot demo-a -AlsoRejectTest
poetry run python -m services.mt5_worker_agent.main verify-broker --broker ic-markets --slot demo-b --env demo
poetry run python -m services.mt5_worker_agent.main capacity
```

## API surfaces

- `GET /broker-connectivity/mt5-broker-registry`
- `GET /broker-connectivity/mt5-servers?broker=` (verified + documented hints + demo/live split)
- `GET /broker-connectivity/mt5-verification-matrix`
- `GET /broker-connectivity/mt5-worker-ops`
- Worker: `capacity`, `queue-status`, `verify-broker --env demo|live`

## Remaining dependencies

1. Approved Demo (+ optional Live auth) credentials per broker with **exact** server names.
2. Successful `verify-broker` on isolated portable terminals (respect capacity=2).
3. Optional apply of `20261109193000_mt5_broker_verification_evidence.sql` for durable Postgres evidence.
4. Larger concurrent multi-user scale still needs more host RAM/disk — **without** claiming unlimited capacity.
