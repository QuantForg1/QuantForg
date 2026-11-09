# MT5 Multi-Broker Gateway — implementation status

**Date:** 2026-11-09  
**Scope:** Broker Accounts refinements + honest multi-broker registry / server discovery

## What is production-verified today

| Capability | Status |
|---|---|
| Weltrade connect via Windows MT5 Gateway | **Operational** (existing Railway → Windows path) |
| Credential encryption at rest (AES-256-GCM) | **Implemented** (`core/security/credential_encryption.py`, `BrokerSecretStore`) |
| Account ownership / claim / reconnect / disconnect | **Unchanged** existing Weltrade APIs |
| Robot / OMS / risk / kill switches | **Unchanged** — no second trading engine |

## What is scaffolded but not live for extra brokers

| Broker | Registry status | Demo verified | Live verified |
|---|---|---|---|
| Weltrade | `production_verified` | Yes (profile + gateway) | Yes (production gateway) |
| Exness | `not_verified` | No | No |
| IC Markets | `not_verified` | No | No |
| Pepperstone | `not_verified` | No | No |
| FP Markets | `not_verified` | No | No |
| HFM | `not_verified` | No | No |
| XM | `not_verified` | No | No |

Connect is disabled in the Broker Accounts UI for any broker with `connectable=false`.

## Infrastructure dependency

MetaTrader 5 requires a **Windows terminal process**. Railway API containers cannot host MT5.

Existing control-plane pieces (do not invent a second Robot):

- `app/application/services/mt5_worker_control_plane.py`
- `app/presentation/routers/mt5_workers.py`
- `docs/architecture/MT5_WORKER_RAILWAY_CONTROL_PLANE.md`
- `docs/architecture/LOCAL_MT5_WORKER_DEPLOYMENT.md`

**Still required before non-Weltrade brokers can be marked verified:**

1. Dedicated Windows VPS / worker hosts with isolated MT5 terminals per account.
2. Approved **demo** credentials for each broker under test.
3. Successful connect + heartbeat evidence recorded, then flip `connectable=true` for that slug.
4. Server discovery feed from the terminal (never invent server names in the UI).

## API surfaces added

- `GET /api/v1/broker-connectivity/mt5-broker-registry`
- `GET /api/v1/broker-connectivity/mt5-servers?broker=<slug>`

Admin → Broker Management shows the registry table without passwords.
