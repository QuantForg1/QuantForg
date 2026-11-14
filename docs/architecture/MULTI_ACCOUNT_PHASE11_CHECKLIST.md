# Phase 11 — Demo auth proof + approved staging dispatch (checklist)

**Status:** IN PROGRESS — prep + first real demo auth (XM) captured 2026-11-14.  
**Blocked until:** Remaining protected `QF_DEMO_*` for other brokers **and** written staging-dispatch approval (section D).  
**Baseline runtime:** current `main` / Railway staging+prod (re-read `/api/v1/version` before D).  
**Evidence:** `docs/production/reports/phase11/PHASE11_PREP_AND_XM_DEMO_AUTH_2026-11-14.md`

## Hard locks (never flip in Phase 11)

```text
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
FORCE_FIRST_TRADE=false
QUANTFORG_M1_MICRO_LIVE_SUBMIT=false
```

Preserve Weltrade LIVE, global Owner risk YAML, P7 `10.0000`, OMS, mandatory SL.  
No Production orders. No real-money tests. Never print/commit/chat credentials.

---

## Prerequisites (Owner)

| # | Prerequisite | Status template |
|---|---|---|
| P1 | Disposable demo MT5 credentials in **protected** Windows host `deploy/mt5_worker_agent/local.env` as `QF_DEMO_LOGIN` / `QF_DEMO_PASSWORD` / `QF_DEMO_SERVER` (or broker-specific `QF_DEMO_<BROKER>_*`) | ◐ XM demo present+verified; 7 other demos missing keys (2026-11-14) |
| P2 | Same material on **staging API** only if sealed-claim path is required for the test | ☐ |
| P3 | Written approval: staging-only `MULTI_ACCOUNT_DISPATCH_ENABLED=true` | ☐ **do not enable until Owner replies** |
| P4 | Staging Railway SHA is current `main` (contains Phase 9 dry-run) | ◐ re-confirm `/api/v1/version` before section D |
| P5 | Portable slots `demo-a`/`demo-b` present; LIVE Program Files terminal untouched | ◐ `demo-a` ready; `demo-b` absent; soft cap 1; LIVE protected |

When P1–P5 are satisfied, execute sections A→F without requesting secrets in chat.

---

## A. Secure credential provisioning

1. Confirm variable **names** exist on host (and staging API if needed); never log values.
2. Confirm `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.
3. Confirm agent `QUANTFORG_API_BASE_URL` points at staging.
4. Confirm `WORKER_SERVICE_TOKEN` length ≥ 16 (redact in all output).

**Exit:** credential presence check green · no secrets in transcripts.

---

## B. Windows portable MT5 authentication

1. `prepare-slots` / ensure `demo-a` portable `terminal64.exe` only.
2. Run `python -m services.mt5_worker_agent.main connect-demo --slot demo-a` (optional `--broker …`).
3. Expect `ok=true`, `trade_allowed` evidence, **no password** in JSON.
4. Refuse if path resolves to Program Files LIVE terminal.

**Exit:** real demo session on portable slot · LIVE terminal untouched.

---

## C. Identity + assignment match

1. Verify login identity matches intended demo account (redacted in reports).
2. Verify broker server string (demo server family).
3. Verify account type = demo (not live).
4. Persist timestamped verification evidence via existing worker report path.
5. `railway-register` + `railway-heartbeat` for the slot.
6. Confirm ops summary: `account_login_verified` / `server_verified` set · `ready` consistent · assignment user/account IDs match worker.

**Exit:** verified demo bound to assigned worker · evidence stored.

---

## D. Owner-approved staging dispatch activation

1. Record approval quote/date/approver in this file or ops log.
2. Set **staging only:** `MULTI_ACCOUNT_DISPATCH_ENABLED=true`.
3. Re-read staging variables: LIVE submit / force-first / micro-live / live-terminal-worker still **false**.
4. Production dispatch flag remains **false**.

**Exit:** staging dispatch on · LIVE path still off everywhere.

---

## E. Controlled staging claim/ACK matrix

Use disposable/lab or verified demo targets only. Prefer delivery-suppressed / non-OMS paths unless a **separate** explicit demo-order authorization exists (default: **no order_send**).

| # | Case | Expected |
|---|---|---|
| E1 | ITE / lab signal → per-account eligibility | ELIGIBLE or BLOCKED with reason |
| E2 | Durable enqueue | job persisted · idempotent key |
| E3 | Assignment-bound claim | correct worker gets job |
| E4 | Spoofed user/account claim | `assignment_mismatch` |
| E5 | ACK | `acked` · `live_submit_allowed=false` |
| E6 | Duplicate signal | same intent · no duplicate execution |
| E7 | Lease recover | recovered ≥ 1 · re-claimable |
| E8 | Fail + retry | pending/dead_letter per policy |
| E9 | Revoked assignment | claim/authorize denied |
| E10 | Stale worker | eligibility blocked |
| E11 | Cross-user isolation | no foreign jobs/data |
| E12 | Kill switch / risk ceiling | blocked · other users unaffected |
| E13 | Queue restart recovery | durable state consistent |
| E14 | Credential authorize/claim (if API seal used) | sealed envelope · no plaintext password field |
| E15 | No LIVE route | prod flags false · no OMS fan-out |

Label each row: **Real demo** | **Staging API** | **Mocked/unit**.

---

## F. Final staging acceptance report

Publish a short report with:

- Staging SHA / deploy ID  
- Demo auth evidence (redacted)  
- Dispatch flag timeline (who/when enabled)  
- Matrix E1–E15 results  
- Orders submitted (must be 0 unless separately authorized)  
- LIVE flags still false  
- Weltrade LIVE status  
- Remaining gaps / Phase 12 recommendation  

---

## Exact next Owner action

1. Place remaining disposable **demo** credentials into protected host `local.env` for brokers still missing (`QF_DEMO_<BROKER>_LOGIN` / `_PASSWORD` / `_SERVER`). **Do not paste into chat.** XM demo already verified 2026-11-14.  
2. Reply with written approval to enable **staging-only** `MULTI_ACCOUNT_DISPATCH_ENABLED=true` before section D.  
3. Do **not** authorize Production multi-account LIVE in this phase.

Until (2), stop after section C prep / additional demo verifies.
