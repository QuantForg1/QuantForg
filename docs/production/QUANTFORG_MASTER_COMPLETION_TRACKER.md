# QuantForg Master Completion Tracker

Living record of every requirement, PR, deployment, blocker and acceptance result. Nothing is marked done without evidence.

Statuses:

- **PRODUCTION VERIFIED**: deployed and observed working in Production.
- **DEPLOYED**: running in Production, acceptance not yet observed.
- **PASS**: verified, but not a deployment.
- **MERGED**, **PR OPEN**, **IN PROGRESS**, **BLOCKED** (with owner action), **NOT STARTED**.

- Last update: 2026-11-16 ~11:55 UTC
- Production backend SHA: `c54e7f51` (Railway deployment `ef57bdc8`, SUCCESS)
- Production frontend SHA: Vercel `frontend` deploys `main`; `/terminal` → `/dashboard` redirect verified live

## Ground truth as of this update (measured, not assumed)

| Fact | Value | Source |
|---|---|---|
| Real-money account connected | 1 (Weltrade-Real, owner) | gateway `/account` |
| Broker accounts in DB | 4 (2 active, 2 revoked), 2 users | `broker_accounts` |
| Multi-account workers / hosts | **0 / 0**. The worker code can now log customers in from the vault (#299), but no Production supervisor runs on the host yet (owner action A5). | `execution_workers`, `worker_hosts` |
| LIVE enablement | ENABLED by the owner 15 Nov 23:45 UTC. The owner chose to keep it running on 16 Nov. Not changed by any release. | `ite_ops_runtime_state.live_trading_audit` |
| LIVE trades 16 Nov (old 20/48/0.20 code) | 20 entries, balance ~$20.69 → $12.30 | `live_trade_journal` |
| Gateway heartbeat | **stalled since 10:18 UTC**. `/history/deals` times out (60–140 s) since ~10:40 UTC. | gateway `/health`, Railway logs |
| Repository visibility | PUBLIC | GitHub |

**Answer to "can many users just enter MT5 login and have the robot trade?": not yet.** No multi-account worker or terminal is provisioned. The only working execution path is the owner's single Weltrade account through the existing gateway. This is workstream **W2**.

## Roadmap order (owner-approved 16 Nov)

1. Core Platform Completion
2. Final Institutional Acceptance
3. Business & Subscription
4. Global Infrastructure & Reliability
5. Compliance & Legal
6. Customer Experience & Growth
7. Global Launch → Global Scale & Institutional Leadership

Continuous Quant Research runs alongside all of these.

Principle: no page-only work. Every change must fix a real operating problem.

## Phase 1 — Core Platform Completion

### P1.1 Risk recovery (owner baseline 9 / 25 / RR 1.5 / $0.45 / Q75 / Mon–Fri 07–17 UTC / 0.01 / 1 position)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Code ceilings and final owner guard on the Weltrade robot and manual paths | **DEPLOYED** | PR #295 → `9543ecbb`; 7/7 CI jobs; 4,996 unit + 2,199 trading-core tests |
| 2 | Pre-trade daily budget (realised + floating + planned ≤ 25%) | **DEPLOYED** | `daily_budget_violation`; `test_owner_daily_budget_and_user_caps.py` |
| 3 | Deposits and withdrawals never erase a loss | **DEPLOYED** | `daily_loss_context`. Withdrawals only lower the base, so they are stricter. |
| 4 | Unknown P/L fails closed | **DEPLOYED** | `OWNER_DAILY_PNL_UNAVAILABLE` |
| 5 | Strictest-wins with the user's saved caps; read failure rejects | **DEPLOYED** | `load_user_live_caps`, `USER_RISK_UNAVAILABLE` |
| 6 | 16 Nov replay: all 20 real entries rejected by the new rules | PASS | `test_owner_baseline_nov16_replay.py` (22 tests) |
| 7 | Production data G1 (runtime v16→v17, platform policy, owner caps, ops overlay) | **DEPLOYED** | Applied 11:0x UTC. Verified: v17 `9/25/1.50/0.45/75/07:00-17:00 Mon-Fri`, experimental removed, platform `9/25/1.5/0.45/75`, owner `9/9/25`, `risk_profile_id` removed. `live_trading_state` unchanged (ENABLED). Rollback: `rollback.sql` + `rollback_pre_apply_state.json`. |
| 8 | Gateway deploy script: exact SHA, flat check, XAUUSD symbol | **DEPLOYED** (script in repo) | `deploy_main_gateway.ps1 -TargetSha`; `test_gateway_deploy_script_safety.py` |
| 9 | Windows gateway running the merged code (gateway-side 9% guard) | **BLOCKED (owner action A1)** | Cloud agent has no Windows shell. Computer use cannot type into terminals. |
| 10 | Multi-account worker path enforces the same guard; environment from MT5 `trade_mode` | **DEPLOYED** (#296 `be337290`) | `test_multi_account_owner_guard.py` (19), `test_worker_account_snapshot.py` (4) |
| 11 | Production runtime observed rejecting with the new codes | NOT TESTED | Needs a session window with a working gateway (A1) |

### P1.2 Product defects (owner screenshots)

| Item | Status | Evidence / root cause |
|---|---|---|
| Remove `/terminal` and all references | **PRODUCTION VERIFIED** (#297 `5378bc10`): `/terminal`, `/workspace`, `/execution` → `/dashboard` in Production; `/execution/diagnostics` 200 | Redirects to `/dashboard`; the order ticket stays on the Dashboard |
| Book large empty gap | **DEPLOYED** (#297) — needs a signed-in visual check | Stretched grid rows → content-sized sections |
| Signals NEUTRAL count ≠ list | **DEPLOYED** (#297), with a contract test | Expired or rejected cards were counted but hidden |
| History "Unable to load…" | **DEPLOYED** (#297): 45 s budget + concurrent reads. Still blocked by the gateway history stall until A1. | 8 s telemetry timeout on a 2–16 s broker read; plus the gateway history stall since 10:40 UTC |

### P1.3 Robot Control Center + account-level controls — DEPLOYED (#300 `c54e7f51`)

- Tables `robot_account_controls` and `robot_control_events` (RLS: owners read their own rows). Applied to Production at 11:4x UTC, before deploy.
- Pause, Resume, Stop, Start and Emergency Stop per account. Every change is audited. Resume and Start re-check real MT5 `trade_allowed`.
- Enforced at the dispatch boundary for new entries on both the engine path and the worker path. Unreadable state fails closed. Controls never close positions.
- `/robot-control-center` sits directly above Risk Center. Route registered in Production (`router=robot_control`).
- NOT TESTED: a signed-in walkthrough in Production. The owner needs to open the page.

- Route `/robot-control-center`, placed directly above Risk Center in the nav.
- Pause, Resume, Stop and Emergency Stop per account, enforced at the dispatch boundary. Stop never closes positions.
- The backend is the source of truth for every state shown.

### P1.4 Multi-user broker connectivity and workers (workstream W2) — IN PROGRESS (audit)

| Item | Status |
|---|---|
| Owner guard on the worker path | DEPLOYED #296 |
| Customer vault credentials reach the slot terminal; READY follows MT5 `trade_allowed`; login-mismatch refused | DEPLOYED #299 `b554403a` |
| Robot controls enforced on the worker path | DEPLOYED #300 |
| Connection state machine: NOT_CONNECTED → … → ROBOT_RUNNING, with trade_allowed / trade_expert evidence | NOT STARTED (audit next) |
| Investor password never counts as trading readiness | NOT STARTED |
| Worker provisioning on the existing Windows host (portable terminals), capacity measurement, queueing | NOT STARTED: 0 workers / 0 hosts |
| Verified per-account commission tariff | **BLOCKER** for multi-account DEMO. Unknown commission rejects entries. |
| Multi-user DEMO acceptance | NOT STARTED |

### P1.5 Other core items — NOT STARTED / to audit

- OMS lifecycle (modify, partial close, reconciliation before retry)
- AI and strategy lifecycle (no unvalidated strategy reaches LIVE)
- Portfolio accuracy
- To verify: MT5 deal times may be broker server time (UTC+2), which would offset the daily window by 2 h. If confirmed, fix it with a test.
- Security: RLS/IDOR audit, credential encryption review

## Phases 2–7 — NOT STARTED

These start after P1 acceptance, in the order above.

Known inputs:
- Billing routes exist (`billing` router). Entitlement enforcement has not been verified.

## Owner actions required

| ID | Action | Why |
|---|---|---|
| **A1** | On the Windows PC, PowerShell as Administrator, in the gateway repo root: `.\deploy\mt5_gateway\deploy_main_gateway.ps1 -TargetSha 9543ecbbcb12ddac99de8f21bf60bc46bdce49d9` | 1. Restarts the stalled gateway: heartbeat stuck since 10:18 UTC, and history times out, which blocks History and the daily-P/L check. 2. Loads the 9% gateway guard. The script refuses to run while a position or order is open. See `docs/production/owner-risk-baseline-2026-11-16/GATEWAY_UPDATE.md`. |
| A2 | Make the GitHub repository private; enable branch protection on `main` | Security (G5) |
| A3 | Give agents a separate bot identity | Security / audit |
| A4 | Per-account verified commission for multi-account DEMO brokers | Required by the risk guard |
| A5 | On the Windows host: create `deploy/mt5_worker_agent/local.production.env` (Production `WORKER_SERVICE_TOKEN`, slot root, `QF_MT5_LOCAL_SLOTS`), then run `prepare_local_slots.ps1` and `start_production_supervisor.ps1` | Brings the multi-user workers online (W2). Current soft cap is 2 portable terminals; capacity must be measured. |
| A6 | Supabase dashboard: enable Leaked Password Protection (Auth) | Security advisor WARN |

## Release log

| Time (UTC) | Change | SHA / ID | Result |
|---|---|---|---|
| 16 Nov 10:59 | PR #295 squash-merged | `9543ecbb` | Merged after 7/7 CI. No open position at merge (gateway `/positions` = `[]`). |
| 16 Nov 11:00 | Railway deploy | `01f39b7d` | SUCCESS. Startup clean. The in-memory LIVE state hydrated as PAUSED (existing restart safety) and waits for gateway ownership probes. |
| 16 Nov ~11:0x | Production data G1 | n/a | Applied and verified (see P1.1 #7) |
| 16 Nov 11:18 | #296 multi-account owner guard | `be337290` | Merged, deployed |
| 16 Nov 11:21 | #297 UI fixes / #298 tracker | `5378bc10` / `a01e4410` | Railway SUCCESS; Vercel READY; redirect verified |
| 16 Nov 11:36 | #299 vault credentials for workers | `b554403a` | Merged, deployed |
| 16 Nov 11:4x | Migration `robot_account_controls` | n/a | Applied (additive; down file in repo) |
| 16 Nov 11:45 | #300 Robot Control Center | `c54e7f51` | Railway `ef57bdc8` SUCCESS; router registered |
| 16 Nov 11:5x | Migration: pin `search_path` on `forbid_self_service_role_change` | n/a | Applied (security advisor 0011) |

## Handoff (next exact actions)

1. A1, the gateway restart, unblocks history, the daily-P/L check and robot entries. The ITE has been held PAUSED since restart, waiting for gateway probes. The heartbeat has been stalled since 10:18 UTC.
2. After A1: watch the logs for `OWNER_*` rejects and confirm `runtime_policy` v17 in the cycle; verify the MT5 server-time day boundary on real deals.
3. W2: connection state machine in the Broker Accounts UI (CONNECTED vs TRADING_PERMISSION_DISABLED vs ROBOT_READY), using worker evidence.
4. Security: RLS/IDOR audit of user-scoped APIs. Advisor: no ERROR-level findings; 1 WARN fixed; 3 SECURITY DEFINER helpers are intended (used by RLS); A6 is pending.
