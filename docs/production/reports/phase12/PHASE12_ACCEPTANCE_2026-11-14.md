# Phase 12 — Production Multi-Account Operational Readiness

**Date (UTC):** 2026-11-14  
**Verdict: NOT COMPLETE**  
**Orders submitted this phase:** **0**  
**Phase 11:** COMPLETE (not re-run)

---

## 1. Production baseline

| Check | Status | Evidence |
|---|---|---|
| `origin/main` SHA | **PASS** | `71bd8900` (docs #266 tip) |
| Railway Production runtime SHA | **PASS** | `a5b4f8e1` (E12/#265) — docs tip ahead only |
| Railway Staging runtime SHA | **PASS** | `a5b4f8e1` |
| Railway Production deployment ID | **PASS** | `97db7979-046a-46c1-8669-5596783cba2b` · Online |
| Railway Staging deployment ID | **PASS** | `5f266d14-4fe4-4598-bb74-57f690dbf0f3` · Online |
| Version `deployment_id` field | **PASS** | Prod/Staging match Railway IDs above |
| Production health live/ready | **PASS** | HTTP 200 / ok |
| Staging health live/ready | **PASS** | HTTP 200 / ok |
| Vercel Production deployment | **PASS** | GitHub Deployments API id `7426110637` (frontend tip may differ from API SHA) |
| Production flags | **PASS** | DISPATCH=true · LIVE_SUBMIT=true (preserved) |
| Staging flags | **PASS** | DISPATCH=true · LIVE_SUBMIT=false (preserved) |
| Host `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | **PASS** | false |
| Host FORCE_FIRST_TRADE / M1 micro | **PASS** | unset⇒false |
| Phase 11 final report | **PASS** | `PHASE11_FINAL_ACCEPTANCE_2026-11-14.md` COMPLETE |
| Admin multi-account ops (Owner JWT, Production) | **PASS** | `/api/v1/multi-account/ops/summary` 200 · `observe_only=true` · no password fields |
| Admin multi-account ops (same JWT, Staging) | **BLOCKED** | HTTP 401 — Staging auth/JWT audience differs from Production Supabase mint |

Artifacts: `.tmp-phase12/phase12_baseline_results.json`, `production_ops_redacted.json`, `owner_ops_read_results.json`

---

## 2. Multi-account isolation

| Check | Status | Evidence |
|---|---|---|
| Control-plane unique user↔account binding (Production) | **PASS** | 6 workers · 6 unique users · 6 unique accounts · 0 duplicates |
| One active Weltrade LIVE ownership row | **PASS** | brokers card: weltrade live active **n=1** · revoked n=2 |
| Cross-user spoof claim rejected | **PASS** | Staging: `assignment_mismatch` |
| Unregistered Production claim denied | **PASS** | HTTP 404 `Worker not found` (fail-closed) |
| Sealed credential authorize (Staging) | **PASS** | `credentials_exposed=false` |
| Sealed claim envelope (Staging) | **PASS** | `sealed=true` · no plaintext password field |
| Ops payloads redact secrets (Prod+Staging) | **PASS** | `credentials_exposed=false` · no password/token leak in ops/stale |
| Ownership domain rule (code + unit) | **PASS** | one non-revoked MT5 account per user · global login uniqueness · 39 related unit tests green |
| Failure isolation (per-user kill / other users continue) | **PASS** | Proven on Staging in Phase 11 E12; unit `test_kill_switch_isolates_one_user` green |
| Production ready workers | **FAIL** | **0 / 6 ready** · **0** login+server verified |
| Production worker freshness | **FAIL** | stale_scan `stale_count=4` · heartbeats dated 2026-11-09/10 |
| `execution_workers` provisioning table | **FAIL** | PG card active/healthy/total **0** (control-plane in-process count=6 only) |

---

## 3. Robot lifecycle (stage audit)

ITE → multi-account path is **planning/dry-run only** and **fail-closed when LIVE_SUBMIT is armed**.

| Stage | Status | Evidence |
|---|---|---|
| Signal generation (ITE) | **PASS** | Singleton Weltrade path remains live; health ok |
| Qualification / decision | **PASS** | Existing ITE runtime unchanged this phase |
| Account eligibility engine | **PASS** | Unit matrix green; customer status forces `live_submit_allowed=false` |
| Customer risk checks | **PASS** | Effective-risk / prefs path unchanged; P7 not modified |
| Global risk / Policy v16 | **PASS** | Not modified; Owner policy surface untouched |
| Durable dispatch enqueue | **BLOCKED** | With Production `LIVE_SUBMIT=true`, `plan_and_enqueue` / ITE dry-run return **`live_submit_armed_refused`** (Phase 9 hard rule) |
| Worker claim | **BLOCKED** | No ready Production workers to claim multi-account jobs |
| Execution authorization → OMS | **BLOCKED** | Queue/ACK explicitly **never** call OMS/`order_send`; no multi-account LIVE fan-out wiring |
| Broker confirmation | **BLOCKED** | Not exercised for multi-account (singleton Weltrade separate) |
| Position protection (PME) | **PASS** | Untouched; kill-switch contract `positions_unaffected` |
| Audit | **PASS** | Owner ops observe-only; Phase 11 E12 audit trail pattern available (staging-only mutate) |
| Idempotency / mandatory SL / reversal guards | **PASS** | Not bypassed; no order tests run |

---

## 4. Broker connection & readiness matrix (Production)

| Broker / surface | Status | Notes |
|---|---|---|
| Weltrade LIVE singleton | **PASS** | `weltrade_singleton_not_shared=true` · 1 active live account row |
| Multi-account portable workers | **FAIL** | 0 ready · 0 verified · lifecycles: provisioning×4, stopped×1, revoked×1 |
| Eight-broker multi-account LIVE | **BLOCKED** | Not production-ready; DEMO proof was Phase 11 only |

---

## 5. Queue & recovery

| Check | Status | Evidence |
|---|---|---|
| Production queue depth / failed / DLQ | **PASS** | depth=0 · failed=0 · dead_letter=0 · kill_switched=0 |
| Delivery latency samples | **BLOCKED** | sample_count=0 (no multi-account deliveries) |
| Staging lease recover (non-prod) | **PASS** | recover ok · recovered=0 · expired=0 |
| Production lease recover | **BLOCKED** | Skipped (mutating; read-only preference) |
| Stale worker detection | **PASS** | `/stale/scan` works Prod+Staging |
| Retry counters surface | **PASS** | cards.retry_counts present |

---

## 6. Emergency controls

| Check | Status | Evidence |
|---|---|---|
| Per-user dispatch kill-switch API | **PASS** | Staging-only Owner mutate (Phase 11 E12); Production mutate refused by design |
| Global ITE kill-switch | **PASS** | Existing `/ite/ops/kill-switch/*` preserved · **not armed** this phase |
| Ops safety hardcodes | **PASS** | Owner/worker ops always report `live_submit_allowed=false` on observe surface |

---

## 7. Security & credentials

| Check | Status | Evidence |
|---|---|---|
| No plaintext passwords in ops/claim/authorize | **PASS** | Runtime probes |
| Sealed envelopes only to assigned worker | **PASS** | Staging claim |
| Flags not silently changed | **PASS** | Prod/Staging match mandated policy |

---

## 8. Defects fixed / PRs

| Item | Status |
|---|---|
| Code defects requiring hotfix | **None verified** this phase |
| Speculative migrations | **Not created** |
| PRs merged for Phase 12 fixes | **n/a** |

Harness notes (not product defects): Railway CLI status parse Unicode on Windows; unregistered claim returns HTTP 404 body (still deny).

---

## 9. Production deployment verification

| Item | Value |
|---|---|
| Runtime SHA | `a5b4f8e1bec83a373959b64906d92580d1aecbc2` |
| Deployment ID | `97db7979-046a-46c1-8669-5596783cba2b` |
| Flags | DISPATCH=true · LIVE_SUBMIT=true |
| Safety observe | live_submit_allowed=false · delivery_suppressed_default=true |
| Orders | **0** |

---

## 10. Remaining blockers — Owner decisions required

1. **Multi-account LIVE fan-out architecture**  
   Production `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true` currently **disables** the multi-account ITE/queue planning path (`live_submit_armed_refused`). Singleton Weltrade LIVE continues separately.  
   **Decide:** keep fail-closed (recommended until OMS fan-out is explicitly designed), **or** authorize a new phase to wire multi-account LIVE submit safely without weakening OMS/SL/idempotency.

2. **Production worker heartbeat / readiness**  
   Control-plane shows 6 stale/non-ready rows; agent host targets **Staging**.  
   **Decide:** whether Production should receive dedicated multi-account worker heartbeats (without touching Weltrade LIVE Program Files), and which customers/accounts are authorized.

3. **`execution_workers` vs control-plane dual registry**  
   PG `execution_workers` remains 0 while `mt5_worker_control_plane` holds 6 rows.  
   **Decide:** accept dual-registry observe note, or authorize a reconciliation/readiness program.

4. **Staging Owner JWT**  
   Production-minted Owner JWT works on Production ops; Staging returned 401.  
   **Decide:** confirm whether Staging uses a separate Supabase/JWT authority (expected) — no change required if intentional.

5. **Deploy docs tip `71bd8900`**  
   Optional Railway redeploy for docs-only SHA parity — not required for trading safety.

---

## Conclusion

Phase 12 **cannot** be marked COMPLETE: Production multi-account workers are not ready/verified, and LIVE_SUBMIT=true intentionally refuses multi-account fan-out planning. Singleton Weltrade LIVE, OMS, flags, and credential isolation remain intact with **0** orders submitted.

**Do not declare Phase 12 complete until Owner decisions (1)–(3) are resolved and Production readiness evidence passes.**
