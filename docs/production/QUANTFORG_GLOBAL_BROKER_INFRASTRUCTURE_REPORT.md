# QuantForg — Global Broker Infrastructure Report

Last updated: 17 Nov 2026, 06:00 UTC. Statuses follow the master tracker:
COMPLETE_VERIFIED · IMPLEMENTED_NOT_VERIFIED · MISSING · BLOCKED_EXTERNAL ·
OWNER_ACTION_REQUIRED · DEFERRED · FAILED. Nothing below is marked verified
without Production evidence.

## 1. Current architecture (as found)

| Component | Where | State (evidence) |
|---|---|---|
| Owner terminal + MT5 gateway | Owner's Windows PC `desktop-o3qdvth`, `gateway.quantforg.com` via Cloudflare | Weltrade-Real **12439799**, heartbeat fresh (`/health` 17 Nov 05:46:23 UTC, age 7.6 s). Runs from worktree `QuantForg-wt-POLICY`, local branch `fix/live-blockers` @ `8774b418` — **this commit is not on GitHub** (see §8). |
| Customer worker supervisor (portable MT5 slots) | Same PC, `C:\QuantForg-Workspace\mt5_worker_slots*` | **Never started in Production**: `worker_hosts` = 0 rows, `execution_workers` = 0 rows (DB 17 Nov). Designed soft cap `QF_MT5_MAX_CONCURRENT_PORTABLES=2`. Owner action A5. |
| API | Railway `europe-west4` | Healthy; shared-terminal operations owner/admin only (#340, #349). |
| Database | Supabase eu-central-1 | No client (anon/JWT) table access; RLS on all 113 public tables (#348, C9). |
| Customer broker registration | `register_customer_account` → `QUEUED_FOR_TERMINAL` | Credentials sealed server-side; customers never touch the owner terminal (#341, #343). |

**Plain answer to "how many customers can be connected at the same time":**
today **0 customers can run on their own terminal**, because the worker
supervisor has not been started. Customers can register accounts (queued).
After A5 the designed limit is 2 concurrent customer terminals on this PC,
and that number is still **unmeasured**. No capacity is claimed beyond that.

## 2. Changes implemented this session

| PR | Change | Status |
|---|---|---|
| #348, migration `20261117013609` | No client table access on Supabase | COMPLETE_VERIFIED (REST 42501) |
| #349 | Customers cannot use shared-terminal execution; emergency stops scoped; platform writes operator-only | IMPLEMENTED_NOT_VERIFIED (needs A14 customer session) |
| #352, #353 | Balance/Equity no longer depend on gateway history; history 4 s budget | COMPLETE_VERIFIED (Broker page 12.3 / 12.3) |
| #356 | Gold First metadata-validated mapping + execution gate + `GET /mt5/gold-mapping` | IMPLEMENTED_NOT_VERIFIED (Prod endpoint check blocked by §7 stall) |
| #357 | Two gateway `/positions` reads that froze the API event loop (91.8 s) moved off the loop | IMPLEMENTED_NOT_VERIFIED (deploying) |

## 3. Gold First — broker-by-broker

Mapping rule (#356): canonical `XAUUSD` maps to one broker symbol only after
live MT5 metadata validates — USD quote; gold in broker metadata
(`currency_base` XAU *or* broker description); gold price band; ounce tick
geometry `tick_value ≈ contract_size × tick_size` for USD accounts; tradable
spec. Name is only a candidate filter. MISSING / AMBIGUOUS / INVALID fail
closed (`GOLD_MAPPING_INVALID`).

| Broker | Actual Gold symbol | Evidence | Status |
|---|---|---|---|
| Weltrade (Real) | `XAUUSD` | Live `/mt5/symbols/XAUUSD` 17 Nov: "Gold Ounce vs US Dollar (Spot)", `currency_base=USD` (!), `currency_profit=USD`, contract 100, digits 3, tick 0.001 → 0.1, vol 0.01/0.01 | COMPLETE_VERIFIED (metadata); gate on live cycle IMPLEMENTED_NOT_VERIFIED |
| XM | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| Exness | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| HFM | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| IC Markets | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| Pepperstone | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| FP Markets | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |
| JustMarkets | not yet observed | Fixture only | OWNER_ACTION_REQUIRED (A14 DEMO) |

Note: the code previously assumed Weltrade gold was `XAUUSD_i`
(`CANONICAL_GOLD_BROKER_DISPLAY`). The live Real server lists `XAUUSD`. The
catalogue resolver already uses the live spelling; the display constant is
legacy and is not used for execution.

## 4. DEMO acceptance checklist (run per broker; DEMO only, no LIVE orders)

Preconditions: owner creates one test customer (A14) and, for each broker, a
DEMO account. The owner types DEMO passwords into the Broker page himself —
never into chat. Worker supervisor running (A5). Robot stays PAUSED for the
owner account throughout.

For each of the 8 brokers record pass/fail, timestamp, and evidence (API
response + Railway log line + DB row; never a screenshot alone):

| # | Step | Pass criteria |
|---|---|---|
| C1 | Connect: choose broker, server from the list, login, master password | Status moves `QUEUED_FOR_TERMINAL` → `CONNECTED` only after the slot reports `account_login_verified` and `server_verified`; no password in any response or log |
| C2 | Connect with wrong password | `AUTH_FAILED`; no worker left half-allocated; previous state untouched |
| C3 | Connect with wrong server | `AUTH_FAILED` / `BROKER_UNAVAILABLE`; nothing saved as connected |
| C4 | Investor (read-only) password | Connected but `trade_allowed=false`, shown as trading not permitted |
| C5 | Same login from a second customer | Rejected: `login_registered_to_another_user` |
| R1 | Reconnect while healthy | Reuses the same slot; no second terminal process |
| R2 | Kill the slot terminal, then Reconnect | Heartbeat goes stale → `RECONNECTING` → `CONNECTED` on the same slot within the backoff budget |
| R3 | Change the password at the broker, then Reconnect | `AUTH_FAILED`; no retry storm (bounded backoff) |
| D1 | Disconnect with no positions | Slot released, lease revoked; recovery does not reconnect it; history and audit kept |
| D2 | Disconnect with an open DEMO position | Position reported to the user; **not closed**; confirmation required |
| X1 | Change account: new DEMO login (valid) | Old connection kept until the new one validates; switch is atomic; old slot released after |
| X2 | Change account: new login (invalid) | Old account stays connected and intact |
| G1 | Gold mapping (`GET /mt5/gold-mapping`) | `VALIDATED` with the broker's real symbol and spec; record it in §3 |
| G2 | Non-gold symbol order attempt by the robot | Rejected `DISABLED_AUTONOMOUS_SYMBOL` |
| I1 | Customer A reads customer B's account / positions / exposure | 403/404 for every route |
| I2 | Customer calls `/execution/submit`, `/weltrade/attach`, `/mt5/connect` | 403 `SHARED_TERMINAL_OWNER_ONLY`; owner terminal login unchanged (gateway `/health`) |
| I3 | Two customers connect at the same time | Two different slots; no session switch on either |
| E1 | DEMO robot round trip (one broker first) | Signal → risk checks → OMS → MT5 DEMO fill → SL/TP set → history → P&L, all on the customer's own slot |

## 5. Concurrent-user capacity test plan (DEMO only)

Do not raise `QF_MT5_MAX_CONCURRENT_PORTABLES` until this has been run.

1. **Baseline** (owner terminal only): sample CPU, RAM, disk free, network
   RTT to the brokers, and gateway `/health` latency every 10 s for 15 min.
2. **Step load**: N = 1, 2, 3, 4, 6, 8 DEMO slots (one DEMO account each,
   brokers mixed). Hold each step 30 min. Per step record: CPU % (avg/p95),
   RAM used and free, per-terminal working set, connect time per slot,
   heartbeat age p95, reconnect success after a forced terminal kill,
   worker failures, queue wait for a 1st queued account, and owner-gateway
   `/health` latency (it must not degrade).
3. **Stop rule**: stop adding slots at the first step where CPU p95 > 70 %,
   free RAM < 25 %, heartbeat p95 > 30 s, owner gateway latency doubles, or
   any slot loses its session.
4. **Safe capacity** = the last passing step minus one (headroom).
   Levels: NORMAL ≤ 70 % of safe capacity; HIGH LOAD 70–100 % (new
   allocations queue); CAPACITY FULL at safe capacity (no new allocations;
   never disconnect existing customers).
5. **Report** fills: current safe concurrent sessions, tested maximum, CPU
   and RAM at capacity, average connection time, reconnect success rate,
   worker failure rate, queue wait time.

### Scaling roadmap (targets to engineer and measure, not claims)

| Target | What it takes |
|---|---|
| ~10 | One dedicated Windows host (not the owner's PC) with the existing supervisor; measured cap per host. Needs owner approval for cost. |
| 100 | Several worker hosts registered in `worker_hosts`, health-based assignment (exists), per-host caps from the measured step test, alerting on host CPU/RAM. |
| 500–1,000 | Host pool with automated provisioning, queue with SLA, per-broker server affinity, centralised log/metrics; Supabase connection pooling review. |
| 10,000 | Different architecture class: broker-side APIs or a hosted MT5 manager/bridge instead of one terminal per account; requires commercial broker agreements. |

## 6. Gateway recovery at `a150730e` — readiness

Runbook: `GATEWAY_RECOVERY_a150730e.md`. Findings this session (read-only):

- The token source is `C:\QuantForg-Workspace\QuantForg-wt-POLICY\.env`; that
  worktree is on local branch `fix/live-blockers` @ `8774b418`, which **is not
  on GitHub**. If this is the running code, the gateway runs unreviewed code
  today. The deploy script records it as `previous_commit` and the commit stays
  in the local repo, so rollback remains possible. Step 1 of the runbook
  (process command line) confirms which checkout is live.
- New symptom (17 Nov 05:44–05:46 UTC): gateway `/positions` calls time out
  while `/health` is fine — same family as the `/history` hang the recovery
  targets.
- Preconditions now also include: owner pause stays in place
  (`owner_paused=true`), automatic resume disabled (#350). Neither is changed
  by the recovery.

## 7. Open issues found this session

| Issue | Status |
|---|---|
| API event loop stalled 91.8 s on gateway `/positions` (startup recovery + exposure) | Fix #357 deployed; verify `event_loop_blocked` absent |
| Gateway `/positions` and `/history/*` hang while `/health` is fine | OWNER_ACTION_REQUIRED (gateway recovery authorization) |
| Vercel Production frozen on #346: Hobby daily deployment limit | #355 (main-only) merged; Production frontend redeploys on the next allowed main build |
| GitHub Actions minutes exhausted | BLOCKED_EXTERNAL; local checks per PR (owner-approved) |

## 8. Owner-only actions (current)

| ID | Action | Status |
|---|---|---|
| A5 | Start the worker supervisor on the Windows host | OWNER_ACTION_REQUIRED |
| A14 | Test customer + one DEMO account per broker | OWNER_ACTION_REQUIRED |
| GW | Authorize gateway recovery at `a150730e` | OWNER_ACTION_REQUIRED |
| A10 | NOWPayments verification | PENDING |
| A11 | Telegram operator Chat ID | PENDING |
| A8 | Backup restore drill | DEFERRED |
| A9 | GitHub Pro | DECLINED |
