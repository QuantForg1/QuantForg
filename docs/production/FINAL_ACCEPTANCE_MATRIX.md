# QuantForg final acceptance matrix

Rechecked against Production on 16 Nov 2026, ~18:50 UTC. Every row cites evidence that was observed, not a previous report.

Statuses:

| Status | Meaning |
|---|---|
| **PASS** | Verified in Production with evidence |
| **CODE PASS** | Implemented and tested in CI, but not yet exercised in Production with real accounts |
| **BLOCKED** | Waits on an owner action (named) |
| **OPEN** | Work remains for engineering |

**Verdict: NOT ACCEPTED.** Customers must not trade yet. Each objective below has a blocking row.

## Current Production facts (queried, not assumed)

| Fact | Value |
|---|---|
| Backend SHA (Railway `7e649d4e`, SUCCESS) | `9b52ce67` |
| Gateway heartbeat | last `2026-11-16T10:18:37Z` (stalled more than 8 h); `/history/deals` times out |
| LIVE state (DB) | ENABLED (owner decision, unchanged); no open positions |
| Users / broker accounts | 41 users; 4 broker accounts, all LIVE; **0 DEMO accounts** |
| Workers / hosts | **0 / 0** |
| Supabase plan | **Pro**: daily backups, last 7 days |
| GitHub | private; branch protection unavailable on the current plan (403) |

## 1. Gateway & workers

| Requirement | Status | Evidence / blocker |
|---|---|---|
| Gateway runs the reviewed SHA `a150730e…` | BLOCKED (owner A1) | Gateway code identical to backend `9b52ce67` (153 imported `app.*` modules unchanged). Procedure: `GATEWAY_RECOVERY_2026-11-16.md` |
| Fresh heartbeat / history / UTC offset / daily loss / gateway 9% guard | BLOCKED (A1) | Post-restart checklist in the recovery doc |
| Worker auth | CODE PASS | Bearer `WORKER_SERVICE_TOKEN`, `hmac.compare_digest`. Railway has the variable (name verified). |
| Registration / heartbeat / stale detection | CODE PASS | Idempotent per host+slot; stale after 45 s (`scan_stale`) |
| Capacity | CODE PASS | `allocate_slot` raises a conflict at `max_terminals`; supervisor soft cap is 2 portables |
| One worker per account and per user; no slot aliasing | CODE PASS | #306, #311, #315 (aliasing bug found by this audit and fixed) |
| Production supervisor running | BLOCKED (owner A5) | 0 hosts in `worker_hosts` |

## 2. Robot completion

| Component | Status | Evidence |
|---|---|---|
| Owner risk baseline on every path (engine, manual, worker, gateway) | CODE PASS; engine path DEPLOYED | Execution-path table in the tracker; 16 Nov replay rejects 20/20 |
| Daily stop: pre-trade, deposits/withdrawals, unknown fails closed, real UTC | CODE PASS (DEPLOYED) | #295, #305. Production check after A1 is pending. |
| Robot Control Center + Pause/Resume/Stop/Emergency | PASS (read-only) | Signed-in Production render: ROBOT_READY / RUNNING. Controls deliberately not clicked on LIVE. |
| Entitlement gate on customer robots | CODE PASS | #316 |
| History / Portfolio | BLOCKED (A1) | Pages honest ("Loading timed out") while gateway history hangs |
| OMS / execution on DEMO (order, SL/TP, close, reconcile) | BLOCKED (A5 + DEMO accounts) | No DEMO execution evidence exists yet |
| Incident / recovery | PASS (one real incident) | API outage 17:1x UTC fixed by #307; health 3–21 ms afterwards |

## 3. Broker connectivity (authentication evidence is not trading readiness)

Evidence: Production `mt5_broker_verification_evidence`, recorded by the owner's Windows verify runs on 14–15 Nov.

| Broker | Authenticated (env, server) | MT5 trade_allowed | DEMO verified | Robot ready (worker + DEMO execution) |
|---|---|---|---|---|
| Weltrade | LIVE, Weltrade-Real | true | no | Owner account only (gateway) |
| XM | DEMO, XMGlobal-MT5 2 | true | **yes** | no |
| IC Markets | LIVE, ICMarketsSC-MT5-3 | true | no | no |
| Pepperstone | LIVE, PepperstoneKE-MT5-Live01 | true | no | no |
| FP Markets | LIVE, FPMarketsSC-Live | true | no | no |
| Exness | authenticated | **false** (`authenticated_trading_not_enabled`) | no | no |
| HFM | authenticated | **false** | no | no |
| JustMarkets | authenticated | **false** | no | no |

No broker is "robot ready" for customers until a customer DEMO account on a worker has executed and reconciled an order.

## 4. Final institutional acceptance: multi-user DEMO test plan

Prerequisites, all owner actions:
- A1: gateway restarted.
- A5: supervisor running with 2 slots.
- A7: three different users (U1, U2, U3) each connect one DEMO account in Broker Accounts, e.g. XM plus two other brokers, using the master password.
- A4: verified commission recorded for each DEMO account.
- An active license or trial for U1–U3.

| # | Step | Pass condition | Evidence |
|---|---|---|---|
| 1 | U1, U2 connect | Each gets a different slot; worker `user_id`/`broker_account_id` match | `/mt5-workers/ops`, supervisor log `slot_rebound` |
| 2 | U3 connects | Queued (no third terminal), queue depth 1 | assignment queue |
| 3 | Login | Slot logs in with the vault credentials; READY only if MT5 `trade_allowed=true` | `slot_provision ready=True trade_allowed=True` |
| 4 | Investor password (U3, deliberately) | TRADING_PERMISSION_DISABLED, never ready | RCC connection state |
| 5 | Wrong password | REQUIRES_USER_ACTION | RCC |
| 6 | Risk guard | An entry violating RR 1.5 or the session is rejected with `OWNER_*` | authorize reasons |
| 7 | DEMO order | One compliant DEMO entry; SL/TP set; position reconciled; closed | worker execution result, journal |
| 8 | Pause U1 | U1 entries blocked (`ROBOT_PAUSED`); U2 unaffected | authorize reasons per user |
| 9 | Resume U1 | Re-checks entitlement and readiness | RCC event |
| 10 | Stop U1 with an open DEMO position | Position not closed; SL/TP still managed | MT5 terminal + journal |
| 11 | Kill U2's terminal | Heartbeat stale at 45 s → DEGRADED; supervisor relaunches; same account re-bound | ops summary |
| 12 | U1 disconnects | Slot retired; U3 assigned | `slot_rebound` |
| 13 | Isolation | U2's JWT cannot see U1's accounts/controls (RLS); worker B cannot open A's envelope | already PASS in Production RLS + #311 |

Simulated now (CI): steps 1, 2, 3 (logic), 6, 8, 9, 12 and 13 are covered by `test_multi_user_isolation_e2e.py`, `test_customer_account_assignment.py`, `test_worker_slot_provisioning.py`, `test_robot_control_service.py`, `test_multi_account_owner_guard.py` and `test_entitlements.py`. Steps 4, 5, 7, 10 and 11 need real terminals.

## 5. Security & reliability

| Item | Status | Evidence |
|---|---|---|
| RLS on all public tables; cross-user reads blocked | PASS | Production JWT test (rolled back): 0 foreign rows; journal and ops state permission-denied |
| Unauthenticated research routes | PASS (fixed) | #303 |
| Vault exposure to user JWTs | PASS (fixed) | migration `20261116180243`: `authenticated` has no SELECT on `broker_credentials` |
| Credential handling | CODE PASS | AES-GCM vault, owner-checked read, per-worker sealed envelope, password never logged or reported |
| Backups | PASS (platform) | Supabase Pro daily backups, 7-day retention (Supabase docs) |
| Restore test | BLOCKED (owner A8) | A restore must target a **new** project ("Restore to a new project"), never Production. Owner approval needed for the cost. |
| Monitoring / alerts | PARTIAL | Telegram operator alerts and network-incident records exist; no external uptime monitor on `gateway.quantforg.com/health` yet (OPEN) |
| Leaked password protection | BLOCKED (owner A6) | Pro plan is already active, so only the toggle is needed |
| Branch protection | BLOCKED (owner: GitHub Pro) | CODEOWNERS is ready (#312) |

## 6. Business readiness

| Item | Status | Evidence |
|---|---|---|
| Plans, checkout, invoices (NOWPayments crypto) | CODE PASS | `billing_service`: plans, checkout, invoice lookup, IPN with HMAC signature, admin plan management, revenue snapshot |
| Payment webhooks (paid / partial / failed / expired / refunded) | CODE PASS | IPN status mapping includes refunded, expired and failed |
| Entitlements enforced server-side | CODE PASS (new) | #316: Resume/Start return 402 without an active license or trial; worker entries rejected |
| Renewals | CODE PASS (new) | #316: renewal reminders queued 72 h before a paid period ends (was never queued) |
| Refunds | Manual via the NOWPayments dashboard; the IPN marks orders `refunded` | Documented; no automated refund API (provider-dependent) |
| Legal pages | PASS (exist) | `/terms`, `/privacy`, `/risk-disclosure` |
| Real commercial payments | BLOCKED (owner) | Provider approval and business verification must be completed before going live |

## 7. Production launch gate

Customer trading may launch only when all of these hold:
- Every BLOCKED row in sections 1–4 is PASS.
- DEMO acceptance steps 1–13 have passed with evidence.
- The gateway runs `a150730e…` and the post-restart checklist has passed.
- Leaked-password protection and branch protection are on.

LIVE customer trading additionally needs a separate owner authorization, because `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` stays off.

## Owner actions

| ID | Action | Unblocks |
|---|---|---|
| A1 | Restart the Windows gateway with `a150730e…` (recovery doc) | History, Portfolio, daily P/L, gateway guard, robot entries |
| A5 | Start the Production worker supervisor (`WORKER_SUPERVISOR_PRODUCTION.md`) | All worker rows |
| A7 | Three different users connect DEMO accounts | DEMO acceptance |
| A4 | Record a verified commission per DEMO account (`POST /api/v1/robot-control/admin/accounts/{id}/verified-commission`) | DEMO entries |
| A6 | Supabase: enable Prevent use of leaked passwords (already on Pro) | Security advisor |
| A8 | Approve a restore drill into a new Supabase project | DR evidence |
| A9 | GitHub Pro, then run the branch-protection command | Governance |
| A10 | NOWPayments production approval + business verification | Real payments |
