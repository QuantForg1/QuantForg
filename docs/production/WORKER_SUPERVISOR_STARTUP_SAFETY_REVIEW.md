# Customer Worker Supervisor — startup safety review (17 Nov 2026)

Status: **prepared, NOT started.** Starting it needs the owner's explicit
authorization (A5). Nothing in this document has been executed.

## 1. What actually exists today (evidence)

- Worker state lives in `public.mt5_worker_control_plane` (7 rows). The
  `worker_hosts` / `execution_workers` tables are empty and unused.
- History: lab runs 9–14 Nov (slots demo-a/b/c, slot-a/b/verify; all now
  `error`/`revoked`/`stopped`). On 15 Nov 10:45 UTC slot **demo-a** on host
  `prod-windows-1` was `ready` with **XM DEMO** login 169740464,
  `XMGlobal-MT5 2`, login and server verified. Its heartbeat is 2 days old.
- The stored label `ready` on that row is stale: the stale scan runs only
  while the supervisor is up. Account eligibility re-checks heartbeat age at
  decision time (`worker_heartbeat_stale`), so a stale worker cannot be
  assigned an account.
- The supervisor and slots run on the owner's PC `desktop-o3qdvth`, the same
  machine as the LIVE gateway and the Weltrade-Real 12439799 terminal.

## 2. Can it touch the owner's LIVE terminal?

| Protection | Where | Status |
|---|---|---|
| Workers only call `mt5.initialize(path=<slot exe>, portable=True)` — never a bare `initialize()` (which would attach to the running LIVE terminal) | `services/mt5_worker_agent/mt5_session.py` | In code, tested |
| Refuse the configured LIVE terminal path | `paths.assert_worker_terminal_path` | In code, tested |
| **New (this PR):** refuse any terminal under a `Program Files` folder, including through a link | same | Tested (broker-branded owner install refused even when `QF_LIVE_MT5_TERMINAL_PATH` is unset) |
| **New (this PR):** refuse any terminal outside `QF_MT5_SLOT_ROOT` | same | Tested; linked slot dirs inside the root still allowed |
| Start script refuses `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=true` | `deploy/mt5_worker_agent/start_production_supervisor.ps1` | In script |
| Customers cannot attach/claim/reconnect the shared terminal via the API | #340, #343 | In Production |

Residual risk: CPU/RAM contention with the LIVE terminal on the same PC
(see §4). A crashed or hung slot terminal does not affect the LIVE
terminal's process, but heavy load can slow the gateway.

## 3. Can it start customer LIVE trading by itself?

No, as long as these hold. Each must be checked right before start:

| Gate | Default | How to verify before start |
|---|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | false (code default) | Railway startup log line `safety_flags` |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | false (also requires dispatch) | `safety_flags` |
| `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` | false — the actual LIVE send lock | `safety_flags` |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | false | `safety_flags` and the start script |
| `LIVE_AUTO_RESUME_ENABLED` | false | `safety_flags` |
| Owner pause | `owner_paused=true` | `ite_ops_runtime_state` |
| Per-customer Robot Control: not entitled / not enabled | off until the customer enables it | `robot_account_controls` |

**Actual Production values** (`safety_flags`, deployment 6a208f72,
17 Nov 10:02:44 UTC):

| Flag | Value |
|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | **true** |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | **true** |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | false |
| `LIVE_AUTO_RESUME_ENABLED` | false |
| `BILLING_LIVE_CHECKOUT_ENABLED` | false |
| `GOLD_ONLY_MODE` | true |

What this means:

- **Customer LIVE orders stay blocked** by a third gate,
  `MULTI_ACCOUNT_OMS_LIVE_ORDER_SEND_ENABLED` (default off; not among the
  Railway variables). Without it every LIVE customer send fails closed
  (`live_order_send_fail_closed`). It is logged in `safety_flags` from the
  next deploy.
- **Customer DEMO orders would run automatically** once a DEMO worker is
  running *and* the robot produces signals. While the owner pause holds, the
  cycle stops before any signal, so nothing is dispatched.
- **Owner decision before starting the supervisor:** keep dispatch on (DEMO
  acceptance needs it) or set `MULTI_ACCOUNT_DISPATCH_ENABLED=false` and
  `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false` until acceptance starts. Changing
  them restarts the API; it does not change the owner pause.

## 4. Resource headroom

Not measured. The PC was offline to this session at review time, and the
gateway health endpoint reports no CPU/RAM. Before start, the owner (or this
session when the PC is connected) records:

- free RAM (each portable MT5 terminal typically uses a few hundred MB),
- CPU idle %, free disk on `C:`,
- gateway `/health` latency for 10 minutes as the baseline.

Start with **one** DEMO slot (`QF_MT5_MAX_CONCURRENT_PORTABLES=1`), watch
the baseline for 30 minutes, then follow the step test in
`QUANTFORG_GLOBAL_BROKER_INFRASTRUCTURE_REPORT.md` §5.

## 5. Start procedure (owner runs; DEMO only)

1. Confirm §3 gates from the latest `safety_flags` log line.
2. Record the §4 baseline.
3. In PowerShell on the PC:
   `$env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL = "false"`;
   `$env:QF_MT5_MAX_CONCURRENT_PORTABLES = "1"`;
   run `deploy\mt5_worker_agent\start_production_supervisor.ps1`.
4. Within 2 minutes: gateway `/health` still shows login 12439799 /
   Weltrade-Real with a fresh heartbeat; a slot row heartbeats in
   `mt5_worker_control_plane`.

## 6. Stop / rollback

1. Stop the supervisor process (Ctrl+C in its window, or end the process).
2. Close slot `terminal64.exe` processes **whose path is under the slot
   root only**. Never end the Program Files terminal.
3. Gateway `/health`: still 12439799 / Weltrade-Real.
4. Nothing to undo in the database: stale workers are ignored by
   eligibility; rows can stay for audit.
