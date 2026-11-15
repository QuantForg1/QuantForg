# Phase 12B — Multi-Account OMS Execution Acceptance

**Date (UTC):** 2026-11-15  
**Merged PR:** https://github.com/QuantForg1/QuantForg/pull/277  
**Merge SHA:** `bf92df453df4e7b1c1da52f9f5e0c39c89635579`  
**Railway Production health:** `bf92df453df4` / status ok (verified post-merge)  
**Follow-up hotfix branch:** `feat/phase12b-oms-execution` (GOLD alias, attach-before-send, pre-send reject classification)

| Gate | Status |
|---|---|
| Code complete (authorize → send → result) | **PASS** |
| CI required checks (PR #277) | **PASS** |
| Merged to `main` | **PASS** (`bf92df45`) |
| Railway Production deployed | **PASS** (`bf92df453df4`) |
| Real DEMO broker response recorded | **PASS** (reject `10027`) |
| Real DEMO fill ticket | **BLOCKED** — portable terminal `trade_allowed=false` (AutoTrading disabled by client) |
| LIVE multi-account order_send | **PASS (fail-closed)** — 0 real-money submits |
| Duplicate re-authorize blocked | **PASS** |
| Idempotent demo enqueue | **PASS** |

---

## 1. Implementation

| Capability | Status |
|---|---|
| Execute-time OMS authorize | PASS |
| DEMO portable `order_send` | PASS (wired; GOLD alias for XM) |
| Broker result → FILLED/REJECTED/UNKNOWN | PASS |
| Uncertain send → UNKNOWN, no blind retry | PASS |
| Pre-send failures → REJECTED (retryable) | PASS (hotfix) |
| SUBMITTING before send | PASS |
| Position reconciliation audit record | PASS (PME not mutated) |
| DEMO enqueue (Production) | PASS |
| LIVE send fail-closed | PASS |

---

## 2. Real DEMO evidence (Production)

**Worker:** `prod-windows-1` / `demo-a`  
**Account:** XM DEMO `XMGlobal-MT5 2` login masked `***0464`  
**Worker id:** `5fb08249-eb47-459a-8ae9-61b38237f974`  
**Intent:** `92fd3cb7-8511-43cd-9382-ac1cc117ec45`

| Step | Result |
|---|---|
| Heartbeat → `dispatch_ready=true` | PASS |
| DEMO enqueue | PASS |
| Claim + execute-authorize (`order_send_allowed=true`) | PASS |
| MT5 attach + symbol resolve (`XAUUSD`→`GOLD` on XM) | PASS |
| Broker `order_send` | **REJECT** retcode **10027**, comment `AutoTrading disabled by client` |
| `execution-result` recorded | PASS — `job_state=rejected`, `execution_outcome=rejected` |
| Re-authorize same intent | PASS — `intent_terminal` / `order_send_allowed=false` |
| Credentials in response | PASS — none |

Terminal probe after attempt: `terminal_trade_allowed=false` while account `trade_allowed=true` / `trade_expert=true`. Owner must enable **Algo Trading** on the portable DEMO terminal for a fill ticket.

Prior attempt also recorded `symbol_select_failed` for raw `XAUUSD` before GOLD alias — proves reject path without inventing fills.

---

## 3. Isolation / security

| Check | Status |
|---|---|
| Assignment-bound claim/authorize | PASS |
| Cross-user mismatch blocked | PASS (unit) |
| Revoked/disabled blocked | PASS (unit) |
| Credential sanitization | PASS |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | false |
| Weltrade Program Files LIVE singleton | untouched |

---

## 4. LIVE safety

| Control | Status |
|---|---|
| `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` default false | PASS |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` policy-only | PASS (preserved) |
| `FORCE_FIRST_TRADE=false` | PASS |
| Global risk / broker catalogue | unchanged |
| Real-money multi-account orders | **0** |

---

## 5. Remaining blockers / Owner actions

1. Enable AutoTrading on portable `demo-a` XM DEMO terminal, then re-run one 0.01 GOLD DEMO order for a **fill ticket**.  
2. Merge hotfix (attach-before-send, GOLD alias, pre-send reject classification) after CI.  
3. Keep LIVE multi-account send locked until separate authorization.  

---

## 6. Verdict

**PARTIAL → functionally integrated in Production**, with **real broker reject evidence**.  
Not 100% complete for “filled ticket” until AutoTrading is enabled on the portable DEMO terminal.
