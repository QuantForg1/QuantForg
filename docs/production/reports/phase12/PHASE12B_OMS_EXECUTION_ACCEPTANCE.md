# Phase 12B — Multi-Account OMS Execution Acceptance

**Date (UTC):** 2026-11-14  
**Baseline:** `41bc9703` (PR #275)  
**Branch:** `feat/phase12b-oms-execution`  
**Verdict: PARTIAL — integration wired; Production DEMO broker proof pending post-deploy**

Orders treated as fills only when `execution-result` records a broker `retcode` / ticket.  
Queue ACK alone is **never** treated as proof of execution.

---

## 1. Actual OMS execution integration

| Stage | Status | Evidence |
|---|---|---|
| ITE / eligibility / risk → durable queue | PASS (prior + preserved) | `DurableDispatchQueue.plan_and_enqueue` never arms LIVE submit |
| Worker claim | PASS | Existing `/dispatch/claim` ownership-bound |
| OMS authorization at execute time | **PASS (new)** | `authorize_worker_execution` + `POST /dispatch/execute-authorize` |
| DEMO MT5 `order_send` on assigned session | **PASS (wired)** | Worker `mt5_order_execute.execute_market_order` after authorize |
| Broker response capture | **PASS (wired)** | `POST /dispatch/execution-result` → `record_broker_execution` |
| Position reconciliation record | **PASS (wired)** | `build_position_reconciliation_record` (audit; PME not mutated) |
| LIVE multi-account `order_send` | **FAIL-CLOSED** | Requires `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` (default false) |

### Gap closed vs PR #275

PR #275 shipped OMS **preview** on claim. Phase 12B adds the missing claim → authorize → worker `order_send` → broker result → queue FILLED/REJECTED path. ACK remains delivery-only.

### Why not singleton `GuardedOmsSubmitPort` / Weltrade adapter

Account-session binding on the singleton LIVE path fails closed on login mismatch. Multi-account DEMO/LIVE must submit on the **assigned portable worker session**, after control-plane authorize (ownership, risk preview, mandatory SL, env gates). Worker `order_send` is sealed behind `order_send_allowed`; LIVE remains fail-closed until `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED`.

---

## 2. Demo order evidence

| Check | Status |
|---|---|
| Production worker `prod-windows-1` / `demo-a` / XM DEMO / `XMGlobal-MT5 2` | Proven dispatch_ready in prior session (`41bc9703`) |
| Controlled DEMO enqueue API | **Wired** — `POST /dispatch/demo-enqueue` (DEMO only; Production allowed) |
| Worker `--execute --env demo` cycle | **Wired** — authorize → order_send → execution-result |
| Live Production DEMO fill ticket | **PENDING** — requires this PR deployed to Railway, then host execute |

**Post-deploy DEMO proof procedure (Owner host):**

1. Deploy API SHA from this PR to Railway Production.
2. Load `deploy/mt5_worker_agent/local.production.env` (gitignored).
3. Heartbeat + verify `dispatch_ready=true` for `demo-a`.
4. `python -m services.mt5_worker_agent.main` with Production env: register/heartbeat.
5. Call demo-enqueue for that `worker_id` (0.01 lot, mandatory SL).
6. `railway-dispatch-poll --execute --env demo` (not `--dry-run`).
7. Capture JSON: `authorization.order_send_allowed`, `broker.retcode`, `broker.order_ticket`, `execution_result.broker_fill`, `position_reconciliation`.
8. Re-run same idempotency key — expect no second fill ticket.

Until that run completes, Phase 12B is **not** marked complete for Demo evidence.

---

## 3. Broker response evidence

| Artifact | Where recorded |
|---|---|
| `retcode` | Job payload + execution-result response |
| `order_ticket` / `deal_ticket` | Job payload; FILLED only when ok |
| Sanitized comment | Strips password/token/secret keys |
| Reject path | `AccountExecutionState.REJECTED` with detail |

Unit coverage: `tests/unit/test_phase12b_oms_execution.py`.

---

## 4. Customer isolation

| Guard | Status |
|---|---|
| Claim scoped to worker user + broker_account | PASS |
| Execute-authorize lease + assignment match | PASS |
| Cross-user ownership mismatch blocks send | PASS (unit) |
| Revocation / customer trading disabled | PASS (unit) |
| No credentials in authorize/result payloads | PASS (sanitize) |
| Shared MT5 / Program Files LIVE for workers | Forbidden (`QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`) |
| One customer kill-switch blocks only that user | PASS (existing queue kill switch) |

---

## 5. Duplicate protection

| Mechanism | Status |
|---|---|
| Signal / job idempotency keys | PASS (existing) |
| `record_broker_execution` idempotent on terminal FILLED/REJECTED | PASS (unit) |
| Demo enqueue idempotency key | Supported on request schema |
| Dry-run never recorded as fill | PASS (worker poll) |

---

## 6. Position reconciliation

| Check | Status |
|---|---|
| Account-scoped observation after broker result | PASS — `position_reconciliation` on execution-result |
| PME lifecycle mutated | **No** (freeze preserved) |
| Tickets available for PME observation | Yes (`order_ticket` / `deal_ticket`) |

---

## 7. Live execution readiness

| Flag / control | Required value | Status |
|---|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | `true` (preserved) | Policy arming only |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | `true` (preserved) | Policy arming only — **not** order_send |
| `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` | `false` (default) | LIVE send fail-closed |
| `FORCE_FIRST_TRADE` | `false` | Preserved |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` | Preserved |
| Ownership + customer opt-in + worker auth + risk + mandatory SL | Required for any future LIVE send | Enforced in authorize |
| Real-money test orders this phase | **0** | By design |

A global LIVE_SUBMIT flag alone does **not** authorize LIVE `order_send`.

---

## 8. Remaining Owner approvals

1. Deploy Phase 12B API to Production Railway.
2. Authorize controlled DEMO execute on `prod-windows-1`/`demo-a` and attach ticket evidence to this report.
3. Keep `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED=false` until a separate Live-money authorization names accounts and risk windows.
4. Optional: additional DEMO accounts — only if Owner supplies credentials; none invented this phase.

---

## 9. Deployment SHA and health

| Item | Value |
|---|---|
| Pre-phase Production baseline | `41bc97038119` (health at Phase 12B start) |
| This PR SHA | *(fill after merge)* |
| Railway Production health SHA | *(fill after deploy)* |
| Vercel | Independent verify after frontend-impacting merges (API-only expected here) |
| CI | Required green before merge |

### Local verification (this branch)

- `pytest tests/unit/test_phase12b_oms_execution.py` — authorize, LIVE fail-closed, ownership, idempotency, ACK≠fill
- Related durable queue tests — green
- Broker catalogue / servers / adapters — **unchanged**
- Risk policy ceilings — **unchanged**

---

## 10. Completion gate

Phase 12B is complete only when **all** are true:

1. CI green + merged + Railway healthy on the merge SHA  
2. DEMO enqueue → authorize → MT5 accept/reject → recorded broker response on Production worker  
3. Duplicate idempotency proven on that path  
4. LIVE path remains fail-closed (`OMS_LIVE_ORDER_SEND` off; zero real-money submits)

Until item 2 is attached, verdict remains **PARTIAL**.
