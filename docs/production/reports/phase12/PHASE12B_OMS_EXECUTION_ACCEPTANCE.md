# Phase 12B — Multi-Account OMS Execution Acceptance

**Date (UTC):** 2026-11-15  
**Baseline:** `41bc9703` (PR #275)  
**Branch:** `feat/phase12b-oms-execution`  
**Head (pre-merge):** see PR #277 latest SHA  
**PR:** https://github.com/QuantForg1/QuantForg/pull/277  

| Gate | Status |
|---|---|
| Code complete | **PASS** |
| CI required checks | **PASS** (Unit Tests, Trading Core Regression; plus Lint/Type/Frontend/Integration) |
| Vercel preview deploy | **BLOCKED** (account build rate-limit; API-only change unaffected for required checks) |
| Merged to `main` | *(update after merge)* |
| Railway Production SHA | *(update after deploy)* |
| Real DEMO broker execution | **NOT TESTED** until post-deploy proof (or **BLOCKED** if credentials/terminal unavailable) |
| LIVE multi-account order_send | **PASS (fail-closed)** — zero real-money submits |

---

## 1. Actual implementation completed

| Capability | Status | Notes |
|---|---|---|
| Execute-time OMS authorize | PASS | `authorize_worker_execution` + `POST /dispatch/execute-authorize` |
| DEMO worker `order_send` | PASS (wired) | Assigned portable session only |
| Broker result → durable state | PASS | `record_broker_execution` → FILLED / REJECTED / UNKNOWN |
| Uncertain `order_send` | PASS | UNKNOWN + `retry_order_send_allowed=false` (no blind retry) |
| SUBMITTING transition | PASS | `mark_submitting` before send |
| Position reconciliation record | PASS | Audit observation; PME not mutated (freeze) |
| DEMO enqueue (Production-safe) | PASS | `POST /dispatch/demo-enqueue` |
| LIVE path checks | PASS | Fail-closed unless `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` |
| Credential sanitization | PASS | Password/token/secret stripped |
| Revoked / disabled customer | PASS | Unit-covered |
| ACK ≠ fill | PASS | Unit-covered |

### Why not singleton Weltrade `GuardedOmsSubmitPort`

Account-session binding fails closed on login mismatch. Multi-account must submit on the **assigned portable worker**, after control-plane authorize.

---

## 2. Execution state vocabulary

| State | Meaning | Evidence source |
|---|---|---|
| QUEUED | Durable delivery pending | Queue |
| CLAIMED | Worker lease | Claim API |
| SUBMITTING | OMS authorized; send imminent | `mark_submitting` |
| FILLED | Broker DONE + ticket | `execution-result` |
| REJECTED | Definite broker reject | `execution-result` |
| UNKNOWN | Uncertain send; **no blind retry** | null/timeout/connection without ticket |
| ACKED (delivery) | Delivery handoff only | Never implies fill |

---

## 3. DEMO terminal / worker evidence

| Item | Status | Evidence |
|---|---|---|
| Production worker host `prod-windows-1` | PASS (prior) | Phase 12A / repair session |
| Slot `demo-a` XM DEMO `XMGlobal-MT5 2` | PASS (prior) | `dispatch_ready=true` with fresh heartbeat |
| Post-deploy controlled DEMO fill ticket | **NOT TESTED** | Requires merge + Railway health on Phase 12B SHA, then host `--execute` |
| Duplicate idempotency on real broker | **NOT TESTED** | Same gate |
| Revocation blocks new submit (live API) | PASS (unit) / NOT TESTED (prod) | |

**Post-deploy DEMO procedure (Owner host, no chat passwords):**

1. Confirm Railway `/health` SHA == merge SHA.  
2. Load gitignored `deploy/mt5_worker_agent/local.production.env`.  
3. Heartbeat → `dispatch_ready=true` for `demo-a`.  
4. DEMO enqueue (0.01, mandatory SL).  
5. `railway-dispatch-poll --execute --env demo` (not dry-run).  
6. Capture masked JSON: retcode, order_ticket, `execution_outcome`, `position_reconciliation`.  
7. Re-enqueue same idempotency key → no second ticket.  

Until step 6 attaches a real ticket, Demo execution acceptance remains **NOT TESTED**.

---

## 4. Customer isolation

| Check | Status |
|---|---|
| Cross-user claim / execute blocked | PASS (unit + lease/assignment checks) |
| Credential leakage in authorize/result | PASS |
| Shared MT5 / Program Files LIVE for workers | Forbidden (`QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`) |
| One-active-account-per-user | Preserved (not weakened) |
| Per-user kill-switch scope | PASS (existing) |

---

## 5. Duplicate / uncertain protection

| Check | Status |
|---|---|
| Job idempotency keys | PASS |
| Terminal FILLED/REJECTED/UNKNOWN idempotent | PASS (unit) |
| Uncertain → no `retry_order_send_allowed` | PASS (unit) |
| Dry-run never recorded as fill | PASS |

---

## 6. LIVE safety

| Control | Value | Status |
|---|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | preserved true | PASS |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | preserved true (policy arm only) | PASS |
| `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` | default **false** | PASS |
| `FORCE_FIRST_TRADE` | false | PASS |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | false | PASS |
| Weltrade LIVE singleton | untouched | PASS |
| Real-money multi-account orders this phase | **0** | PASS |
| Global risk ceilings | unchanged | PASS |
| Broker catalogue / servers / adapters | unchanged | PASS |

---

## 7. CI / quality

| Check | Status |
|---|---|
| Lint & Format | PASS |
| Type Check | PASS |
| Unit Tests | PASS |
| Trading Core Regression | PASS (required) |
| Frontend Lint Typecheck Build | PASS |
| Integration Tests | PASS |
| Vercel deploy status | FAIL / rate-limit (not a required status check) |

Local: `test_phase12b_oms_execution.py` + durable queue suite green after uncertain-outcome hardening.

---

## 8. Remaining Owner approvals

1. Merge PR #277 (required checks green; Vercel rate-limit is known non-required).  
2. Confirm Railway Production SHA.  
3. Run controlled DEMO execute on `prod-windows-1`/`demo-a` and attach ticket evidence.  
4. Keep `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED=false` until a separate Live-money authorization.

---

## 9. Completion gate

Phase 12B is **fully** complete only when:

1. Merged + Railway healthy on merge SHA — *(pending)*  
2. Real DEMO enqueue → authorize → MT5 result → recorded ticket — *(pending)*  
3. Duplicate idempotency proven on that path — *(pending)*  
4. LIVE remain fail-closed — **PASS**

**Current verdict: PARTIAL** — code + required CI complete; Production DEMO broker proof pending post-deploy.
