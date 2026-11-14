# Phase 12A — Production worker readiness & registry reconciliation

**Date (UTC):** 2026-11-14  
**Verdict: NOT COMPLETE** (investigation + observability shipped; Production still has **0** dispatch-ready workers)  
**Orders submitted:** **0**  
**Parent:** Phase 12 remains NOT COMPLETE  
**Flags preserved:** Prod DISPATCH=true / LIVE_SUBMIT=true · Staging DISPATCH=true / LIVE_SUBMIT=false · fail-closed `live_submit_armed_refused` unchanged

---

## 1. Root cause — all six Production workers

Runtime source: `GET /api/v1/mt5-workers/ops/summary` (Production). Host agent `QUANTFORG_API_BASE_URL` → **Staging**.

| # | worker_id (prefix) | host / slot | lifecycle | Primary not-ready causes |
|---|---|---|---|---|
| 1 | `0e6e6b4a` | _(empty)_ | **revoked** | `revoked` · `reconnect_requested` · no host/slot · hb 2026-11-09 |
| 2 | `8c2ed28e` | windows-local-01 / slot-b | **stopped** | `stopped` · **heartbeat_missing** · login/server not verified |
| 3 | `23e641dd` | windows-local-01 / slot-verify | **error** | `heartbeat_stale` (2026-11-09) · login/server not verified |
| 4 | `d59b8b6b` | local-windows-1 / demo-a | **error** | `heartbeat_stale` (2026-11-10) · login/server not verified |
| 5 | `d9c2e686` | local-windows-1 / demo-b | **error** | `heartbeat_stale` (2026-11-10) · login/server not verified |
| 6 | `22646a81` | local-windows-1 / demo-c | **error** | `heartbeat_stale` (2026-11-10) · login/server not verified |

### Common systemic cause

| Finding | Status |
|---|---|
| Agent targets Staging, not Production | **PASS** (explained) — `local.env` `QUANTFORG_API_BASE_URL` contains staging |
| No Production heartbeats since ~Nov 9–10 | **FAIL** for readiness |
| No `account_login_verified` / `server_verified` on any Prod row | **FAIL** for dispatch readiness |
| Weltrade LIVE Program Files not used as worker slot | **PASS** (protected) |
| Staging workers ≠ Production-ready | **PASS** (documented; not assumed) |

**Aggregate:** lifecycle ready **0/6** · dispatch-ready **0/6**.

---

## 2. Production worker onboarding readiness

| Check | Status | Notes |
|---|---|---|
| Written onboarding procedure | **PASS** | `docs/architecture/MULTI_ACCOUNT_PHASE12A_REGISTRY_AND_ONBOARDING.md` |
| Dedicated Production agent env exists | **BLOCKED** | Host still points at Staging; Owner must authorize Production-target agent |
| Portable slot capacity on host | **PASS** | demo-a present; LIVE terminal allow=false |
| Fabricated auth/readiness | **PASS** | None claimed |

---

## 3. Registry reconciliation

| Check | Status | Evidence |
|---|---|---|
| Control plane authoritative for agent runtime | **PASS** | Phase 8 note + migrations + ops `execution_workers_note` |
| `execution_workers` = Phase-1a assignment registry | **PASS** | migration comment; FK to users/accounts |
| Why EW count=0 while CP=6 | **PASS** | Agent writes CP; EW not written by lab register; agent→Staging |
| Auto sync / backfill required now | **PASS** (not required) | Would risk FK violations on lab UUIDs |
| Competing sources of truth introduced | **PASS** | None; docs clarify single runtime authority |
| Speculative migration | **PASS** | Not created |

Field mapping: see onboarding/registry doc §1.

---

## 4. JWT environment findings

| Check | Status | Evidence |
|---|---|---|
| Prod vs Staging Supabase hosts differ | **PASS** | Prod `otqyhlmwaifokrczryrc…` · Staging `saxsyobktmlyjghumxfz…` |
| Staging 401 with Prod-minted Owner JWT | **PASS** (expected) | Separate JWT authorities by design |
| Validation weakened / secrets shared | **PASS** | Not done |

---

## 5. Operational readiness (read-mostly)

| Check | Status | Evidence |
|---|---|---|
| Flags unchanged | **PASS** | Railway vars + ops feature_flags |
| Per-user isolation / sealed creds | **PASS** | Phase 11+12 evidence retained; no re-open |
| Stale detection | **PASS** | `/stale/scan` + error lifecycle |
| Monitoring: not_ready_reasons on ops | **PASS** | Code + unit tests (this PR) |
| Production dispatch-ready workers | **FAIL** | Still 0 |
| Multi-account OMS wiring | **PASS** | Not wired; fail-closed preserved |
| Orders | **PASS** | 0 |

---

## 6. Tests and deployment

| Item | Status |
|---|---|
| Unit: `tests/unit/test_phase12a_worker_not_ready_reasons.py` | **PASS** (CI on PR #269) |
| Observability: `not_ready_reasons`, `dispatch_ready`, reason counts in ops | **PASS** |
| PR / merge | [#269](https://github.com/QuantForg1/QuantForg/pull/269) → `a95bb71c` |
| Production + Staging runtime SHA | **PASS** `a95bb71c` |
| Production ops after deploy | **PASS** `dispatch_ready_count=0` · `not_ready_count=6` · reason counts include `heartbeat_stale`, `login_not_verified`, `server_not_verified`, `revoked`, `stopped`, `lifecycle_error` |
| LIVE_SUBMIT / DISPATCH flags flipped | **No** |

---

## 7. Remaining external / Owner decisions

1. **Authorize a Production-targeted Windows agent env** (separate from Staging `local.env`) for portable slots only — or explicitly defer Production multi-account workers.  
2. **Do not** point the existing Staging agent at Production without a written cutover (would starve Staging heartbeats).  
3. **Do not** backfill `execution_workers` from control-plane lab rows without a dedicated ownership-bound provisioner design.  
4. Phase 12 overall COMPLETE still requires Owner decisions on LIVE fan-out architecture (unchanged fail-closed).

---

## Conclusion

Phase 12A delivered **root-cause evidence**, **registry clarification**, **JWT authority confirmation**, **onboarding procedure**, and **ops observability** for not-ready reasons.  

**Phase 12A is NOT COMPLETE** until at least one Production portable worker is evidence-backed `dispatch_ready=true` **or** Owner explicitly defers Production worker onboarding.  

**Phase 12 remains NOT COMPLETE** regardless.
