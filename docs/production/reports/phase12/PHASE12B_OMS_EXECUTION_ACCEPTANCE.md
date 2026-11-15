# Phase 12B — Multi-Account OMS Execution Acceptance

**Date/time (UTC):** 2026-11-15T10:45:20Z  
**Deployment SHA:** `7bc43aca88dd` (Railway Production health **ok**)  
**Merged implementation:** PR #277 `bf92df45`, PR #283 `7bc43aca`  
**Docs PR:** https://github.com/QuantForg1/QuantForg/pull/285  

| Gate | Status |
|---|---|
| Code / CI / deploy | **PASS** |
| Terminal path discrepancy resolved | **PASS** (junction — same underlying dir) |
| Algo Trading enabled | **PASS** (`terminal_info.trade_allowed=true`) |
| Single DEMO order submitted | **PASS** (exactly one) |
| DEMO fill ticket + reconciled position | **REJECTED** by MT5 (`10018` Market closed) |
| LIVE multi-account order_send | **PASS (fail-closed)** — unchanged; 0 real-money submits |

**Final acceptance decision: REJECTED — MT5 EXECUTION REJECTED**

---

## 1. Terminal path verification

| Item | Evidence |
|---|---|
| Configured root | `C:\QuantForg-Workspace\mt5_worker_slots_production` |
| Configured slot path | `...\mt5_worker_slots_production\demo-a` |
| Link type | **Junction** → `C:\QuantForg-Workspace\mt5_worker_slots\demo-a` |
| Resolved executable | `C:\QuantForg-Workspace\mt5_worker_slots\demo-a\terminal64.exe` |
| Attached session path | `C:\QuantForg-Workspace\mt5_worker_slots\demo-a` |
| Same underlying directory | **true** |
| Portable process | PID **15520**, `/portable` (not Program Files LIVE) |
| Host / slot / worker | `prod-windows-1` / `demo-a` / `5fb08249-eb47-459a-8ae9-61b38237f974` |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` |
| Weltrade LIVE Program Files | **Not used** |

Path mismatch from earlier probes is explained: production path is a junction to the portable data directory. OMS attach and Algo Trading apply to the **same** terminal instance.

---

## 2. Preflight checklist

| Check | Result |
|---|---|
| Railway health SHA | `7bc43aca88dd` ok |
| Worker `dispatch_ready` | **PASS** |
| Login masked | `***0464` (`169740464`) |
| Server | `XMGlobal-MT5 2` |
| Account DEMO (`trade_mode=0`) | **PASS** |
| Account `trade_allowed` | **true** |
| Terminal Algo Trading `trade_allowed` | **true** |
| `tradeapi_disabled` | **false** |
| GOLD visible + bid/ask | **PASS** (bid `3882.55`, ask `3883.08`) |
| No open GOLD positions/orders before send | **PASS** |
| OMS authorize `order_send_allowed` | **true** |
| Volume | `0.01` |
| Symbol | `GOLD` |
| Mandatory SL present | **PASS** (adjusted at send to `3879.19692`) |
| Unique idempotency key | `demo:phase12b:fill:f384f5c456…` |
| LIVE flags modified | **No** |

---

## 3. Single DEMO order result

| Field | Value |
|---|---|
| Intent / OMS job | `327ef1eb-a2df-4523-bc0c-e85d27768356` |
| Side | BUY |
| Volume requested | `0.01` |
| Symbol executed path | `GOLD` |
| `order_send` attempted | **Yes** (exactly one) |
| MT5 retcode | **10018** |
| MT5 comment | `Market closed` |
| Order ticket | none |
| Deal ticket | none |
| Request price | `3883.08` |
| Broker result price | `0.0` (reject) |
| Stop loss (sent) | `3879.19692` |
| OMS final state | **`rejected`** |
| `execution_outcome` | `rejected` |
| Position after | none |
| Duplicate re-authorize | **blocked** (`intent_terminal` / `order_send_allowed=false`) |
| Second order submitted | **No** |

### Reconciliation

OMS recorded broker reject (`retcode=10018`) with `position_reconciliation.filled=false`. No GOLD position exists on the terminal. No UNKNOWN state; no retry performed.

---

## 4. LIVE safety recheck

| Check | Status |
|---|---|
| Weltrade LIVE terminal touched | **No** |
| Real-money order | **0** |
| `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` | unchanged / fail-closed |
| Production/Staging safety flags changed | **No** |
| Other users’ sessions | unaffected |

---

## 5. Prior evidence retained

Earlier AutoTrading-off reject (`10027`) remains valid historical evidence that the OMS→MT5→result path works. Fill acceptance still requires an actual deal when the market is open.

---

## 6. Owner follow-up for PASS fill

When XM GOLD market is open on this DEMO account, re-run **one** 0.01 GOLD order with the same preflight. Do not retry while market-closed rejects persist.

---

## 7. Verdict

**REJECTED — MT5 EXECUTION REJECTED** (`10018` Market closed) after full preflight PASS and a single authorized DEMO `order_send`.  
Not PASS (no ticket/deal). Not UNKNOWN. LIVE remained fail-closed.
