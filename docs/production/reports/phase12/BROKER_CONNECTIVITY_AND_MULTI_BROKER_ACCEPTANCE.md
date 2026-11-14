# Broker Connectivity & Multi-Broker Execution — Acceptance

**Date (UTC):** 2026-11-14  
**Program verdict: NOT COMPLETE** (connection-state consistency shipped; Production worker readiness still blocked)  
**Orders submitted:** **0**  
**LIVE money risk:** unchanged · fail-closed `live_submit_armed_refused` preserved  
**Flags:** Prod `MULTI_ACCOUNT_DISPATCH_ENABLED=true` / `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true` · Staging DISPATCH=true / LIVE_SUBMIT=false — **not flipped**

---

## 1. Broker connection bug — root cause and fix

### Root cause

UI mixed **three authorities**:

| Surface | Prior source | Failure mode |
|---|---|---|
| Top toast | `/weltrade/health` probe → `GATEWAY_UNAVAILABLE` copy said “Broker connection offline” | Treated gateway unreachable as full account offline |
| Broker Accounts hero | Session ownership (`broker === "Connected"`) | Showed “MT5 Account Connected” whenever a session row was owned |
| Connection / Data Sync chips | `gatewayOnline \|\| connected` and `connected ? "Real-time"` | Over-claimed Active / Real-time; ignored sync freshness |
| Trading Permission | Live authorization (`LIVE_DISABLED`) | Correct — but visually conflicted with “Connected” |

`LIVE_DISABLED` is **not** a connection failure. Connected ≠ Trading Enabled.

### Fix (this program)

1. Backend `/trading/session` now returns authoritative `connection_layers`:
   - `linked` · `terminal_started` · `authenticated` · `market_data` · `synced` · `dispatch_ready` · `trading_permitted` · `not_ready_reasons` · `summary`
2. Frontend `resolveBrokerConnectionLayers` + Broker Accounts badges consume those layers.
3. Toast copy no longer says “Broker connection offline” for gateway probe failures — it says gateway unreachable and that the account link may still be saved.
4. Connection chip requires authenticated + synced + gateway/terminal evidence. Data Sync no longer fakes “Just now” / “Real-time”.
5. Connect success toast only says Connected when `authenticated` is confirmed.

**Status:** **PASS** for contradiction fix in code. Deploy verification pending merge.

---

## 2. Connection state consistency

| Layer | Meaning | Display rule |
|---|---|---|
| Linked | Credentials/ownership row exists | “Linked” — not Connected |
| Terminal started | MT5 attached / login > 1 | Required for Active |
| Authenticated | Owned session + balance present | Required for Connected badge |
| Market data | Live catalogue available | Separate chip / reasons |
| Synced | Heartbeat/status healthy + last_verified | Data Sync |
| Dispatch ready | Multi-account worker path | `false` on singleton Weltrade path |
| Trading permitted | Risk + LIVE authorization | Separate from Connected |

Top notification, Broker page, and session presentation now share the same layer model (with legacy fallback when `connection_layers` absent).

**Status:** **PASS** (implementation). End-to-end Production UI proof after deploy: **BLOCKED** until merge.

---

## 3. Production worker onboarding

| Item | Status | Notes |
|---|---|---|
| Separate Production env template | **PASS** | `deploy/mt5_worker_agent/local.production.env.example` |
| Separate Production supervisor script | **PASS** | `start_production_supervisor.ps1` refuses Staging URL / LIVE override |
| Staging `local.env` left intact | **PASS** | Documented isolation in README |
| Production `WORKER_SERVICE_TOKEN` configured on host | **BLOCKED** | Owner must supply Production token (not invented) |
| Outbound HTTPS to Production Railway | **BLOCKED** | Requires host run of Production supervisor |
| Host/slot register on Production | **BLOCKED** | Depends on token + host |
| Fresh Production heartbeats | **FAIL** | Prior audit: stale since ~2026-11-09/10 |
| DEMO auth on portable slot → Production | **BLOCKED** | Needs DEMO credentials + Production agent |
| ≥1 Production `dispatch_ready=true` | **FAIL** | Still 0 from Phase 12A evidence |

Weltrade LIVE Program Files terminal: **not touched**.

---

## 4. Authenticated Production demo workers

| Metric | Value |
|---|---|
| Production dispatch-ready workers | **0** |
| Production DEMO authenticated this session | **0** |
| Fabricated readiness | **None** |

---

## 5. Eight-broker verification matrix

Evidence preserved from Phase 11 DEMO matrix (`PHASE11_DEMO_AUTH_MATRIX_2026-11-14.md`).  
**This session did not re-run live DEMO authentications** (no Production agent + credentials available).

| Broker | Implemented (adapter/registry) | Demo authenticated (prior evidence) | Production worker ready | Execution tested on demo (this program) | LIVE authorized |
|---|---|---|---|---|---|
| Weltrade | PASS | PASS (prior) | FAIL | BLOCKED | FAIL (singleton LIVE only; multi-account LIVE not authorized) |
| XM | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| Exness | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| HFM | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| JustMarkets | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| IC Markets | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| Pepperstone | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |
| FP Markets | PASS | PASS (prior) | FAIL | BLOCKED | FAIL |

Do **not** claim all brokers Production-ready.

---

## 6. Broker server discovery

| Check | Status |
|---|---|
| Exact-server customer entry | PASS (Broker UI manual server field retained) |
| Discovery catalogue path | PASS (existing registry/discovery) |
| Universal single server name assumed | PASS (not assumed) |
| Fresh Production discovery re-proof this session | BLOCKED (needs worker/gateway session) |

---

## 7. Multi-user concurrency

| Check | Status |
|---|---|
| Isolation design (per-account worker/slot) | PASS (architecture retained) |
| Concurrent Production DEMO proof this session | BLOCKED |
| Cross-user credential access | PASS (no change weakening seals) |
| Multi-account OMS fan-out | FAIL / refused — `live_submit_armed_refused` kept |

---

## 8. Connection latency

| Stage | Finding |
|---|---|
| Catalogue probe in `/trading/session` | Already bounded (`wait_for` 2.5s) — retained |
| Fake Connected for speed | Not done |
| Progress copy | Updated to Validating → Authenticating → Synchronizing |
| Measured before/after Production timings | **BLOCKED** (needs deploy + instrumented DEMO connect) |

---

## 9. Registry reconciliation

Unchanged from Phase 12A:

- Authoritative runtime: `mt5_worker_control_plane`
- `execution_workers` = ownership assignment registry (not agent heartbeat store)
- No auto-backfill

**Status:** **PASS** (docs + prior PR #269 observability)

---

## 10. Signal-to-execution lifecycle

| Step | Status |
|---|---|
| Central signal generation | Retained (frozen core) |
| Per-customer eligibility planning | Present in multi-account design |
| Multi-account LIVE submit fan-out | **BLOCKED** — fail-closed until separate Owner OMS release |
| Real-money orders this program | **0** |

---

## 11. Risk and OMS verification

| Policy | Status |
|---|---|
| Max lot / SL mandatory / R:R / daily loss / exposure | Preserved (no weakening) |
| Grid / martingale / averaging / M1 LIVE / auto-reverse | Remain disabled |
| P7 10% customer preference + Owner policy | Untouched |
| `live_submit_armed_refused` | Preserved |

---

## 12. Production deployment SHA and health

| Check | Value |
|---|---|
| Production `/api/v1/health` at report time | `ok` · commit `a6a52e458b0f` |
| This branch baseline | `687f535d` (from `origin/main` at branch create; main may have moved) |
| This program’s code on Production | **Not yet** — pending PR merge + Railway deploy |
| Weltrade LIVE singleton health | Not intentionally disturbed; no LIVE terminal override |

---

## 13. Remaining blockers / infrastructure

1. **Owner action:** create `local.production.env` with Production `WORKER_SERVICE_TOKEN` and approved DEMO credentials; run `start_production_supervisor.ps1` on Windows host with portable slots only.  
2. **Prove** ≥1 Production worker `dispatch_ready=true` with login/server verified (not heartbeat-only).  
3. **Re-verify** eight-broker DEMO auth against Production-targeted workers.  
4. **Merge + deploy** connection-state PR; re-check UI contradiction on `https://www.quantforg.com/broker`.  
5. **Paid Windows VPS:** only if existing host cannot run an additional Production-targeted agent alongside Staging without capacity risk. Cost: Owner-approved Windows VPS (~market rates for 2–4 vCPU / 8–16 GB; not purchased here).  
6. **Separate Owner release** required before multi-account LIVE OMS fan-out — Production `LIVE_SUBMIT=true` does **not** authorize unverified fan-out.

---

## Tests run (this branch)

| Suite | Result |
|---|---|
| `pytest tests/unit/test_phase49_trader_ux.py --no-cov` | **9 passed** (includes `connection_layers`) |
| `node … trader-ux.test.ts` | **ok** |
| Real-money / LIVE multi-account orders | **not run** (forbidden) |

---

## Overall

| Theme | Verdict |
|---|---|
| Connection-state contradiction | **PASS** (code) / deploy proof pending |
| Phase 12A Production `dispatch_ready≥1` | **FAIL / BLOCKED** |
| Broker-neutral Production readiness | **BLOCKED** |
| Cloud MT5 multi-customer at scale | **PARTIAL** (architecture + Production agent scaffolding) |
| Multi-user LIVE execution | **BLOCKED** (intentional fail-closed) |

**Program is NOT 100% complete.** Critical Production worker readiness remains blocked on Owner credentials/host targeting, not on missing connection-state modeling.
