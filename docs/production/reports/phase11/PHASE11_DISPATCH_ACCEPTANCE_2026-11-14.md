# Phase 11 — Staging dispatch acceptance (DISPATCH ENABLED)

**Date (UTC):** 2026-11-14  
**Verdict: NOT COMPLETE** — E1–E15 real Staging matrix is green except **E12** (per-user kill-switch mutate), which is blocked on missing Owner permission (see below).  
**Orders submitted:** **0**  
**Evidence artifact:** `.tmp-phase11/phase11_e_matrix_results.json` (host-local; not committed secrets)

---

## Owner flag mandate (observed, not inferred)

| Flag | Production (runtime ops) | Staging (Railway + runtime ops) | Action this session |
|---|---|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | **true** | **true** (was false → set true) | Kept / enabled per Owner; **not** disabled |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | **true** (authorized Production policy) | **false** | **Not changed** on Production |
| `FORCE_FIRST_TRADE` | false | false | Unchanged |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | n/a host/false | **false** (set explicitly) | Kept false |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | false | false | Unchanged |

Runtime probes (ops/summary + `/api/v1/version`), not PR #259 alone:

- Production SHA: `b310c5e303cc…` — health ok — `credentials_exposed=false`
- Staging SHA: `b310c5e303cc…` — health ok — deploy `edfebd0c…` after seal-env redeploy — `credentials_exposed=false`
- Host agent: `QUANTFORG_API_BASE_URL` → staging; live-terminal worker false

---

## Prerequisites

| # | Item | Result |
|---|---|---|
| P1 | Protected demo creds on host `local.env` | Present (values not logged) |
| P2 | Staging API seal material `QF_DEMO_*` | Pushed to Staging Railway (presence-only); redeployed |
| P3 | Staging `MULTI_ACCOUNT_DISPATCH_ENABLED=true` | **Enabled** per Owner order |
| P4 | Staging SHA current with Phase 9+ | `b310c5e3` matches Production tip |
| P5 | Portable `demo-a`; LIVE Program Files untouched | Observed; Weltrade singleton not used for lab |

---

## Sealed credentials + identity binding

| Check | Result |
|---|---|
| Worker register + heartbeat → staging | PASS |
| Assignment user/account binding | PASS |
| `credentials/authorize` — authorized, no password field | PASS |
| `credentials/claim` — `sealed=true`, envelope present, no plaintext password | PASS |
| Ops `credentials_exposed` | false |

---

## E1–E15 real Staging matrix

Evidence type = **Staging API** unless noted. Lab path is delivery-suppressed; `live_submit_allowed=false` on enqueue/claim/ack.

| # | Case | Status | Notes |
|---|---|---|---|
| E1 | Lab signal → eligibility | **PASS** | `job_count=1` |
| E2 | Durable enqueue | **PASS** | idempotency key persisted |
| E3 | Assignment-bound claim | **PASS** | correct worker/account |
| E4 | Spoofed claim | **PASS** | `assignment_mismatch` |
| E5 | ACK | **PASS** | `delivery_status=acked` |
| E6 | Duplicate signal | **PASS** | idempotent `jobs=1` |
| E7 | Lease recover | **PASS** | `recovered=1` |
| E8 | Fail + retry | **PASS** | `pending` |
| E9 | Revoked worker | **PASS** | revoke → claim/authorize denied; worker re-registered |
| E10 | Stale worker scan | **PASS** | `stale_count≥1` via `/stale/scan` |
| E11 | Cross-user isolation | **PASS** | job bound to assignment; spoof rejected |
| E12 | Kill switch / risk ceiling | **BLOCKED** | see permission gate |
| E13 | Queue restart recovery | **PASS** | recover metrics include `kill_switched` key |
| E14 | Credential authorize/claim | **PASS** | sealed envelope; no password JSON field |
| E15 | No LIVE route | **PASS** | staging live submit false; lab `live_submit_allowed=false` |

**Summary:** pass **31** auxiliary/H/F/C/E rows · fail **0** · blocked **1** (E12).

---

## E12 — exact permission gate (stopped only this test)

Per-user multi-account kill-switch mutation lives on `DurableDispatchQueue.set_kill_switch` (in-process). There is **no** worker-token HTTP route to set it. Global ITE `/ite/ops/kill-switch/arm` was **not** armed (would halt the trading plane; out of Phase 11 scope).

**Required to finish E12 on real Staging:**

1. **Owner JWT** (designated owner) **and**
2. Either an existing Owner-authenticated mutate API for per-user dispatch kill-switch, **or** explicit Owner approval to add a **staging-only** ops route that calls `set_kill_switch` without touching global ITE kill-switch.

Until then E12 remains BLOCKED; all other authorized Phase 11 staging work continued.

---

## Safety preserved

- No unauthorized real-money `order_send`
- Staging LIVE submit remains false
- Production LIVE submit left at authorized **true** (not flipped)
- `FORCE_FIRST_TRADE=false`, micro-live false, live-terminal worker false
- Weltrade LIVE singleton not shared / not used as lab slot
- OMS / Policy v16 / P7 / SaaS / billing not modified this session

---

## Remaining gap → Phase 11 COMPLETE criteria

1. Unblock **E12** with Owner JWT + kill-switch mutate path (above).  
2. Re-run E12 only; attach evidence; then flip checklist Status to COMPLETE.

**Do not mark Phase 11 COMPLETE until E12 real Staging evidence passes.**
