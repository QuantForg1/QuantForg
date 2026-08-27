# Reboot / session-survival validation (manual operator procedure)

This document is **observability and recovery procedure only**.
It does **not** reboot production. It does **not** send orders.

Do not run `Restart-Computer`. Do not call Execute Now. Do not place a test order.

Topology:

```
Owner PC / owner Wi-Fi / browser / Cursor / SSH  — NOT on the execution path
Railway (Linux)  — ITE scanner, Decision, Risk, Safety, Optimizer, OMS, API
Windows VPS us-host-421124  — MT5 + Gateway + Cloudflared + watchdog
```

A running `terminal64.exe` is **not** `EXECUTION_PATH_READY`.
Broker session after VPS reboot is **`MT5_SESSION_RECOVERY_UNPROVEN`** until
`/health` shows connected + login/session + AutoTrading.

Read-only checks on the VPS:

```
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\verify_production_vps.ps1
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\verify_reboot_readiness.ps1
```

For each scenario record: EVENT, DETECTED, RECOVERY, TIME/BOUND, TRADING STATE,
FAIL-CLOSED STATE, DUPLICATE RISK, RESULT.

| EVENT | How to test (manual) | Expected detection | Expected recovery | Bound | Trading state | Fail-closed | Duplicate risk | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. Owner PC off | Power off the personal PC only | None required on VPS/Railway | None | n/a | Unchanged | Existing gates | None | PASS if Railway+VPS stay up |
| B. Owner Wi-Fi off | Disconnect home Wi-Fi only | None required | None | n/a | Unchanged | Existing gates | None | PASS if Railway+VPS stay up |
| C. Browser closed | Close all browsers | None required | None | n/a | Unchanged | Existing gates | None | PASS |
| D. Cursor closed | Close Cursor | None required | None | n/a | Unchanged | Existing gates | None | PASS |
| E. SSH disconnected | Close SSH/RDP tools except if they were the only interactive session | Watchdog continues via Task Scheduler | Watchdog 2 min | 2 min | Unchanged if processes survive | Existing gates | None | PASS if tasks are AtStartup/AtLogOn |
| F. Gateway crash | Stop the Gateway python process only (not production-automated) | `/health/live` fail, listener missing | Watchdog starts one listener, max 8/hour | ≤45s start + 2 min schedule | New entries blocked until Gateway live | Yes | Hashes + request_id | Manual only |
| G. MT5 crash | Stop terminal64 only (not production-automated) | PROCESS_MISSING | start_mt5_terminal.ps1, no duplicate | ≤20s process + session unproven | Fail closed until BROKER_CONNECTED | Yes | None from spawn | Manual only |
| H. Temporary network outage | VPS or Railway WAN blip | public live fail and/or broker disconnect | Cloudflared SCM restart; do not spawn extra Gateway/MT5 | minutes | No stale-tick execution | Yes | No blind order_send retry | Manual only |
| I. Cloudflared restart | Restart-Service Cloudflared | public live fail, local live ok | Automatic service + SCM restart | ~60s SCM | Local Gateway preserved | Tunnel-only is not Gateway restart | None | Manual only |
| J. Railway ITE process crash | In-process watchdog | watchdog_restarts, BACKOFF | run_forever restart, no order_send | ≤30s backoff | Recovery blocks new entries until cycles advance | Yes | Durable hashes | Observe logs |
| K. Railway container restart | Platform restart | healthcheck `/health/live` | restartPolicy ALWAYS | platform | Hydrate hashes from Postgres; reconcile MT5 book | Yes if hashes unverified | Durable hashes | Observe deploy |
| L. VPS reboot | **MANUAL TEST ONLY — do not run from this repo** | Boot → autologon → tasks | Software recovery if AUTO_LOGON=READY | operator | SESSION_RECOVERY_UNPROVEN until /health proves session | Yes | None from watchdog | Operator |
| M. RDP disconnect | Disconnect RDP without logging off | Processes should keep running if session stays | None if session kept | n/a | Unchanged | Logoff can kill interactive MT5 | None | Observe |
| N. RDP reconnect | Reconnect RDP | Same PIDs preferred | Adopt healthy listener, do not restart | n/a | Unchanged | Existing gates | Duplicate spawn forbidden | Observe |

LIVE ORDER SENT during this procedure must remain **NO**.
MT5 TICKET must remain **NONE** unless a real autonomous fill already existed.
