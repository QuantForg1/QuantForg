# MT5 Multi-Broker Gateway — implementation status

**Date:** 2026-11-09  
**Scope:** Windows MT5 multi-broker gateway — Exness + HFM demo first

## What is production-verified today

| Capability | Status |
|---|---|
| Weltrade connect via Windows MT5 Gateway | **Operational** (existing Railway → Windows path) |
| Credential encryption at rest (AES-256-GCM) | **Implemented** (`core/security/credential_encryption.py`, `BrokerSecretStore`) |
| Account ownership / claim / reconnect / disconnect | **Unchanged** existing Weltrade APIs |
| Robot / OMS / risk / kill switches | **Unchanged** — no second trading engine |
| Worker control plane (Railway) | **Present** (`/api/v1/mt5-workers/*`) |
| Local Windows portable slots | **Prepared** on developer host (`demo-a`, `demo-b`) |
| Verification evidence gate | **Implemented** — `connectable=true` only after real Windows verify |

## Broker verification matrix

| Broker | Registry status | Demo verified (real MT5) | Live verified | Connectable |
|---|---|---|---|---|
| Weltrade | `production_verified` | Yes (profile + gateway) | Yes (production gateway) | **Yes** |
| Exness | `not_verified` | **No** — demo credentials not provided | No | **No** |
| HFM | `not_verified` | **No** — demo credentials not provided | No | **No** |
| IC Markets | `not_verified` | No | No | No |
| Pepperstone | `not_verified` | No | No | No |
| FP Markets | `not_verified` | No | No | No |
| XM | `not_verified` | No | No | No |

Connect is disabled in the Broker Accounts UI for any broker with `connectable=false`.

## Windows VPS / host decision

| Option | Verdict |
|---|---|
| Railway Linux containers | **Cannot** run `terminal64.exe` |
| Existing developer Windows host | **Reusable** for portable demo slots (tight RAM/disk) |
| Dedicated Windows VPS | **Required** before multi-user production scale; not provisioned in this phase |

LIVE Program Files Weltrade terminal must **not** be used by multi-broker workers.

## Authenticated demo accounts (this host)

| Metric | Value |
|---|---|
| `QF_DEMO_EXNESS_*` configured | No |
| `QF_DEMO_HFM_*` configured | No |
| Authenticated Exness demo sessions | **0** |
| Authenticated HFM demo sessions | **0** |
| Orders submitted | **0** (LIVE submit remains off) |

## Documented search hints (NOT verified servers)

Copied from broker documentation for admin diagnostics only:

- **Exness:** `Exness-MT5Trial*`, `Exness-MT5Real*` (exact shard from Personal Area)
- **HFM:** `HFMarketsGlobal-Demo`, `HFMarketsGlobal-Live1`, … (exact name from myHF / welcome email)

These hints never appear as verified production servers until a Windows login returns `account_info.server`.

## How to verify a demo (operator)

```powershell
# local.env: QF_DEMO_EXNESS_LOGIN / PASSWORD / SERVER  (exact PA server)
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker exness -Slot demo-a -AlsoRejectTest
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker hfm -Slot demo-b -AlsoRejectTest
```

On success, evidence is written and the broker may flip `connectable=true`. On missing credentials the command exits non-zero with `demo_credentials_not_provided`.

## API surfaces

- `GET /api/v1/broker-connectivity/mt5-broker-registry`
- `GET /api/v1/broker-connectivity/mt5-servers?broker=<slug>`
- `GET /api/v1/broker-connectivity/mt5-worker-ops` (Admin)
- `POST /api/v1/mt5-workers/verification/report` (worker token)
- `GET /api/v1/mt5-workers/ops/summary` (worker token)

## Remaining dependencies

1. Approved Exness + HFM **demo** credentials (login, master password, exact server).
2. Successful `verify-broker` on an isolated portable terminal.
3. Optional dedicated Windows VPS when scaling beyond this host.
4. Additive migration `20261109193000_mt5_broker_verification_evidence.sql` applied when durable API evidence is required.
