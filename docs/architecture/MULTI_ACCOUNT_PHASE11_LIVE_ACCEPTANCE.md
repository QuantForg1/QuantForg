# Phase 11 — LIVE Broker Connection Acceptance (Eight Brokers)

**Status:** Eight-broker integration shipped; **0 / 8** `VERIFIED_LIVE` after sequential portable auth.  
**Date (UTC):** 2026-11-13  
**Branch:** `feat/eight-broker-justmarkets`  
**Canonical order:** Weltrade → XM → Exness → HFM → JustMarkets → IC Markets → Pepperstone → FP Markets  

> Selectability ≠ LIVE-connected. Credential presence ≠ authenticated. DEMO ≠ LIVE.

---

## A. Release evidence

| Item | Value |
|---|---|
| Base `main` | `26b603b8` (Phase 11 docs + PR #244/#245) |
| Feature branch | `feat/eight-broker-justmarkets` |
| Integration doc | `MULTI_ACCOUNT_EIGHT_BROKER_INTEGRATION.md` |
| CI / deploy | Recorded on PR after required checks |

---

## B. Eight-broker LIVE results (portable `demo-a`, sequential)

Credential checker: all eight `QF_LIVE_*` triples **READY_TO_VERIFY** (values never printed).  
Safety: `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`, `FORCE_FIRST_TRADE=false`, `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.  
Capacity: soft cap 1 portable; Weltrade LIVE Program Files protected; `available_now=1`.  
Orders submitted: **0**.

| Broker | Credentials present | MT5 auth | trade_mode | Final status |
|---|---|---|---|---|
| Weltrade | Yes (`QF_LIVE_WELTRADE_*`) | Fail `-6 Authorization failed` (portable; singleton not used) | — | `AUTHENTICATION_FAILED` |
| XM | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| Exness | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| HFM | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| JustMarkets | Yes (`QF_LIVE_JUSTMARKETS_*`) | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| IC Markets | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| Pepperstone | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |
| FP Markets | Yes | Fail `-6` | — | `AUTHENTICATION_FAILED` |

**Genuine `VERIFIED_LIVE`: 0 / 8.**

### Blocker note

MT5 portable initialize returned `(-6, 'Terminal: Authorization failed')` for every broker. Credentials are present and non-empty, but the terminal rejected authorization (wrong password/server for the portable terminal, missing broker server pack, or terminal IPC). Owner must confirm each LIVE login/server against the broker Personal Area and re-run:

```powershell
.\deploy\mt5_worker_agent\check_broker_credentials.ps1
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env live
```

Do not mark `VERIFIED_LIVE` until `trade_mode=2` and broker identity match.

---

## C. Infrastructure

| Item | Observation |
|---|---|
| Windows host | Existing (no new VPS) |
| Portable soft cap | 1 |
| Free RAM (pre-run) | ~1199 MB |
| Disk free | ~2.51 GB (tight) |
| Weltrade LIVE singleton | Protected / not used as test slot |
| New VPS | Not provisioned |

---

## D. Safety

```text
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
FORCE_FIRST_TRADE=false
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
```

Orders submitted: **0**.

---

## E. Remaining blockers

1. Resolve MT5 `-6` authorization failures (credential/server accuracy vs portable terminal readiness).  
2. Re-run sequential LIVE verify after fix; require `trade_mode=2`.  
3. Disk free ~2.5 GB — free space before further terminal installs.  
4. Weltrade production singleton remains `NOT_TESTED` for isolated re-proof (by design).

---

## F. Conclusion

Eight-broker catalogue, JustMarkets adapter, canonical ordering, credential checker, and tests are implemented.  
**0 of 8** brokers have genuine successful LIVE authentication evidence at this writing.
