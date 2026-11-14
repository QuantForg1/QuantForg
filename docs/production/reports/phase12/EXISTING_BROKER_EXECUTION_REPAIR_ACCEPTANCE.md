# Existing Broker Execution Repair — Acceptance

**Date (UTC):** 2026-11-14  
**Verdict: PARTIAL** — planning refuse gate repaired; Production `dispatch_ready≥1` and OMS `order_send` fan-out remain blocked  
**Orders submitted:** **0**  
**Broker catalogue / servers / adapters:** **unchanged** (no re-verification campaign)  
**Flags preserved:** Prod `MULTI_ACCOUNT_DISPATCH_ENABLED=true` · `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true` · `FORCE_FIRST_TRADE=false` · `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`

---

## 1. Actual execution blocker and root cause

| Rank | Blocker | Verdict |
|---|---|---|
| R1 | `live_submit_armed_refused` refused **all** multi-account ITE/queue planning whenever LIVE_SUBMIT=true | **PASS** (fixed) — planning now allowed; queue still never arms submit |
| R2 | Claim/ACK never called OMS / `order_send` | **BLOCKED** — OMS **preview** added; broker submit still unwired by design |
| R3 | Production workers `dispatch_ready=0` (agent historically → Staging) | **BLOCKED** — Production env file prepared on host; readiness proof pending portable DEMO auth against Production |
| R4 | Singleton Weltrade remains sole LIVE `order_send` path | **PASS** (preserved) |

Audit confirmation: [execution path audit](b51531a4-5bb3-45f8-a70d-60a18eea6a2a).

### Fix shipped

1. `DurableDispatchQueue.plan_and_enqueue` — removed refuse-when-armed; keeps `live_submit_allowed=False` on jobs.
2. `run_ite_multi_account_dry_run` — records `live_submit_flag` but continues planning.
3. `preview_oms_authorization` — fail-closed OMS gate check without `order_send`.
4. `dispatch_claim` — returns `oms_authorization` preview + `order_send=false`.
5. Job payload now carries `entry` / `stop_loss` / `take_profit` / `volume` for OMS preview.

---

## 2. Existing broker verification evidence reused

| Item | Status |
|---|---|
| Eight brokers treated as already VERIFIED | **PASS** — prior Phase 11 DEMO matrix reused |
| Catalogue verification ≠ customer auth | **PASS** — customer connection/worker session still required |
| No new broker verification campaign | **PASS** |

---

## 3. Broker / server catalogue unchanged

| Check | Status |
|---|---|
| Broker names | Unchanged |
| Server catalogue entries | Unchanged |
| Adapters replaced | No |
| Capabilities rewritten for tests | No |

---

## 4. Production worker readiness count

| Metric | Value |
|---|---|
| Production `WORKER_SERVICE_TOKEN` | Present (Railway; value not printed) |
| Staging `local.env` | Preserved (untouched) |
| `local.production.env` on host | Created (gitignored) targeting Production |
| Production `dispatch_ready` proven this session | **0** / **BLOCKED** |
| Weltrade LIVE Program Files | Not used as worker slot |

---

## 5. Demo and Live connection support

| Check | Status |
|---|---|
| Customer Demo/Live selection preserved | **PASS** (existing connect path) |
| No silent Demo↔Live conversion | **PASS** |
| Multi-broker connect via exact server | **PASS** (existing) |
| Multi-account LIVE `order_send` | **BLOCKED** (OMS fan-out not wired) |

---

## 6. Multi-user isolation

| Check | Status |
|---|---|
| Per-account claim binding | **PASS** (existing) |
| Cross-user routing | Fail-closed on assignment mismatch |
| Concurrent Production DEMO proof | **BLOCKED** (no dispatch-ready worker) |

---

## 7. Dispatch and queue

| Check | Status |
|---|---|
| Plan/enqueue with LIVE_SUBMIT=true | **PASS** (unit) |
| Jobs force `live_submit_allowed=false` | **PASS** |
| Claim/ACK delivery-only | **PASS** (preserved) |

---

## 8. OMS routing

| Check | Status |
|---|---|
| OMS authorization preview | **PASS** (unit) |
| Preview never sets `order_send=true` | **PASS** |
| Broker fill via multi-account OMS | **BLOCKED** |

---

## 9. Broker response / reconciliation

| Check | Status |
|---|---|
| Multi-account broker fill reconciliation | **BLOCKED** (no submit) |
| Real-money test orders | **0** |

---

## 10. Risk protection

| Check | Status |
|---|---|
| Global Owner policy / P7 / OMS / SL / idempotency | Untouched |
| Grid / martingale / averaging / M1 LIVE / FORCE_FIRST_TRADE | Remain disabled |
| Kill-switch / Weltrade singleton | Preserved |

---

## 11. Latency

| Check | Status |
|---|---|
| Idempotent connect dedupe (existing) | Retained |
| Catalogue probe timeout on session (existing) | Retained |
| Measured before/after Production timings | **BLOCKED** |

---

## 12. Production deployment SHA

| Item | Value |
|---|---|
| Baseline at repair start | `9976fe85` (also later main may move) |
| This repair PR | Pending merge |
| Post-deploy health | Verify after merge |

---

## 13. Remaining Owner actions

1. Keep Staging `local.env` as-is.  
2. Run `deploy/mt5_worker_agent/start_production_supervisor.ps1` with portable DEMO slot (not Program Files LIVE).  
3. Prove ≥1 Production worker `dispatch_ready=true` (fresh heartbeat + login/server verified).  
4. Authorize a separate OMS fan-out wiring phase before any multi-account LIVE `order_send`.  
5. Do not treat catalogue VERIFIED as customer-session ready.

---

## Tests

| Suite | Result |
|---|---|
| `test_phase9_ite_multi_account_dry_run` + `test_phase61_durable_dispatch_queue` + `test_multi_account_oms_authorization` | **29 passed** |
| Real-money / LIVE multi-account orders | Not run |

---

## Overall

| Theme | Verdict |
|---|---|
| Refuse-when-armed incorrectly blocking authorized DISPATCH path | **PASS** (fixed) |
| Existing brokers re-verified | **N/A** (not done — by Owner instruction) |
| Production dispatch-ready workers | **FAIL / BLOCKED** |
| Multi-account OMS `order_send` | **BLOCKED** |
| Completion (connect → ready → signal → execute) | **NOT COMPLETE** |
