# Windows VPS deployment (repository automation)

This document prepares a **QuantForg Windows trading host**. It does **not**
prove that any VPS is healthy. Scripts must be executed **on that host**.

Railway (Linux) continues to run the API and ITE worker. MetaTrader 5 cannot
run on Railway.

## Intended topology

```
Windows VPS (always-on)
  Task Scheduler
    QuantForgMT5Terminal  -> terminal64.exe (no duplicate start)
    QuantForgMT5Gateway   -> supervise_gateway.ps1 -> services.mt5_gateway.main
  MetaTrader 5 (logged-in broker session)
  Gateway bound to 127.0.0.1:8765 + token auth
  Existing secure tunnel (Cloudflare or equivalent)  -->  Railway MT5_GATEWAY_BASE_URL

Railway QuantForg API / ITE
  existing Risk / Safety / OMS / PME  (unchanged)
```

Closing the operator browser or personal PC must not stop this host.
Broker session rules, Risk, Safety, and MIN_LOT still apply.

## What the repo already did vs what a human must do

Repository automation (this clone):

- Supervisor with single-instance mutex, bounded backoff, `/health/live` restart only
- Task templates: AtStartup + AtLogOn, IgnoreNew, no execution time limit
- MT5 start helper that refuses a second `terminal64.exe`
- Delayed AUTO_ATTACH if Gateway starts before the terminal is logged in
- Local verify / recover scripts that never call `order_send`

Human actions **on the VPS** (not performed by this documentation):

1. Log into the VPS desktop as the trading user.
2. Open MetaTrader 5 once and leave it logged in (save password in the terminal UI if that is your policy).
3. Put `MT5_GATEWAY_TOKEN` in the VPS `C:\QuantForg\.env` (never commit it).
4. Enable **auto-logon** for that trading user if you need reboot recovery without RDP (Windows setting; this repo does not write auto-logon passwords).
5. Point the existing tunnel origin at `http://127.0.0.1:8765` (do not publish `:8765` publicly).
6. On Railway, keep `MT5_GATEWAY_BASE_URL` = public HTTPS origin of that tunnel.
7. On Railway, keep `MT5_GATEWAY_CALLER_TOKEN` identical to Windows `MT5_GATEWAY_TOKEN`.
8. Run the commands below **on the VPS**, then `verify_production_vps.ps1`.

This checkout does **not** know the VPS IP, tunnel hostname, or any secret.

## Verification invariant

`verify_production_vps.ps1` requires **exactly one LISTENING owner of `127.0.0.1:8765`**
plus `/health/live` OK. A Windows venv launcher PID plus its child, both showing
`-m services.mt5_gateway.main`, is **one Gateway tree**, not a duplicate server.

Interactive Task Scheduler is **not** enough for unattended reboot. Enable
auto-logon for the trading user if the supervisor must survive reboot without RDP.
This repo does not store Windows passwords or switch Gateway to session-0/S4U
(that would isolate it from the interactive MT5 terminal).

## Commands on the VPS

From an elevated PowerShell:

```powershell
cd C:\QuantForg
git fetch origin main
git checkout main
git pull origin main

# One-shot idempotent install (safe to run twice)
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\deploy_production_vps.ps1

# Health (PASS/WARN/FAIL) — no orders
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\verify_production_vps.ps1
```

If `.venv` deps are incomplete:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\deploy_production_vps.ps1 -InstallDeps
```

## Railway variables (names only)

Set on Railway (values stay in Railway; never paste them into git):

| Variable | Purpose |
|----------|---------|
| `MT5_GATEWAY_BASE_URL` | HTTPS origin that reaches the Windows Gateway (tunnel). |
| `MT5_GATEWAY_CALLER_TOKEN` | Must match Windows `MT5_GATEWAY_TOKEN`. Alias `MT5_GATEWAY_TOKEN` is also accepted. |

Windows Gateway process (VPS `.env` only):

| Variable | Purpose |
|----------|---------|
| `MT5_GATEWAY_TOKEN` | Bearer for Gateway REST. |
| `MT5_GATEWAY_HOST` | Must stay `127.0.0.1`. |
| `MT5_GATEWAY_PORT` | `8765`. |
| `MT5_TERMINAL_PATH` | `C:\Program Files\MetaTrader 5\terminal64.exe` |
| `MT5_GATEWAY_AUTO_ATTACH` | `true` on a private VPS with a logged-in terminal. |

Do not put broker login/password in Railway. Do not put Gateway tokens in git.

## Recovery tests (operator-controlled)

Allowed (scripts in `recover_production_vps.ps1`):

- `-Action Status`
- `-Action RestartGateway`
- `-Action RestartSupervisor`
- `-Action RestartMt5` (optional; restarts the terminal process only)
- `-Action ReclaimPort`

Forbidden: BUY, SELL, Execute Now, `order_send`, SL/TP edits, forced live execution.

Do **not** reboot from code. If you test reboot recovery:

1. Confirm auto-logon is enabled (human).
2. Reboot the VPS from the provider panel (human).
3. After boot, RDP in and run `verify_production_vps.ps1`.
4. Expect: one `terminal64.exe`, one Gateway on `:8765`, `/health/live` ok.
5. `/health` `mt5.connected` may lag until AUTO_ATTACH succeeds.

## Duplicate process rules

- Gateway: port `:8765` + supervisor mutex + task `IgnoreNew`
- MT5: `start_mt5_terminal.ps1` exits if `terminal64` is already running
- Never run two Gateways against the same broker account

## Logs (no secrets)

`docs/production/reports/gateway_supervisor/`

- `supervisor.log` — supervisor start, Gateway start/restart, mutex, MT5 wait
- `gateway.out.log` / `gateway.err.log` — Gateway process
- Delayed attach in Gateway logs: `delayed_auto_attach_ok` / `mt5_unavailable`

Do not enable `MT5_GATEWAY_AUTH_DEBUG=true` except for a short local debug window.
