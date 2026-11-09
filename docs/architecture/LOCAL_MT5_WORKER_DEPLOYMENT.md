# Local Windows MT5 Worker Deployment (Phase 1B local)

Uses the **existing developer Windows machine**. No paid VPS in this phase.

## Compatibility (audited on this host)

| Check | Result |
| --- | --- |
| OS | Windows 10 (win32 10.0.19045) |
| Official MT5 | `C:\Program Files\MetaTrader 5\terminal64.exe` present |
| LIVE terminal process | PID observed running — **must not be used by workers** |
| Python | 3.13 via Poetry; `MetaTrader5` package available in Poetry env |
| Disk | Tight (~2–3 GB free after three portable copies) — prepare slots only with ≥2 GB free |
| Railway | Outbound HTTPS client; no inbound public worker ports |

## Measured local run (2026-11-09, this machine)

| Metric | Observed |
| --- | --- |
| Portable slots prepared | `demo-a`, `demo-b`, `demo-c` under `C:\QuantForg-Workspace\mt5_worker_slots\` |
| Concurrent portable `terminal64` processes | 3 started successfully (`/portable`) |
| LIVE Program Files process | Remained running (untouched by start/stop) |
| Approx RAM / portable terminal | ~230–250 MB working set each (idle, no login) |
| Host free RAM with 3 portables + LIVE | ~1.1 GB (8 GB host — tight) |
| Authenticated demo accounts | **0** — `QF_DEMO_*` credentials not provided |
| Railway outbound health | `GET /api/v1/health/live` → `{"status":"ok"}` with bearer token configured |
| Claimed multi-user LIVE readiness | **No** — terminals started; real login not demonstrated |
| Frontend `npm run build` on this host | Failed `ENOSPC` with ~2 GB free after three portable copies — free disk before CI-style frontend builds |

**Quality gate on this PR (local):** worker unit tests pass; `ruff`/`black`/`mypy` clean for agent modules; `tsc --noEmit` clean. Frontend production build blocked by disk, not by TypeScript errors.

## Product isolation

- Slot root default: `C:\QuantForg-Workspace\mt5_worker_slots\`
- Each slot is a **portable** copy launched with `/portable`
- Workers refuse the LIVE Program Files path unless `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=true` (forbidden for normal use)

## Setup

```powershell
cd C:\QuantForg-Workspace\QuantForg
copy deploy\mt5_worker_agent\local.env.example deploy\mt5_worker_agent\local.env
# Edit local.env: WORKER_SERVICE_TOKEN, optional QF_DEMO_* for connect-demo

.\deploy\mt5_worker_agent\prepare_local_slots.ps1
poetry run python -m services.mt5_worker_agent.main start-slots
poetry run python -m services.mt5_worker_agent.main status
.\deploy\mt5_worker_agent\start_local_supervisor.ps1
```

### Real demo authentication (not mock)

```powershell
# Generic one-shot
$env:QF_DEMO_LOGIN="..."
$env:QF_DEMO_PASSWORD="..."
$env:QF_DEMO_SERVER="..."
poetry run python -m services.mt5_worker_agent.main connect-demo --slot demo-a

# Broker-specific (writes verification evidence; may flip connectable)
# QF_DEMO_EXNESS_LOGIN / PASSWORD / SERVER  — exact Personal Area server
# QF_DEMO_HFM_LOGIN / PASSWORD / SERVER     — exact myHF server
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker exness -Slot demo-a
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker hfm -Slot demo-b
.\deploy\mt5_worker_agent\health_check.ps1
```

If credentials are absent, the command exits non-zero and reports
`demo_credentials_not_provided` — it does **not** invent success.
Exness/HFM stay `connectable=false` until a real portable MT5 login succeeds.

## Railway communication

- Outbound only: `QUANTFORG_API_BASE_URL` + `WORKER_SERVICE_TOKEN`
- `railway-ping` hits `/api/v1/health/live`
- Phase 1C: `railway-register` / `railway-heartbeat` call durable `/api/v1/mt5-workers/*` routes (see `MT5_WORKER_RAILWAY_CONTROL_PLANE.md`)
- Requires the same `WORKER_SERVICE_TOKEN` configured on Railway; plaintext passwords are never returned by the API

## Future VPS migration (no rewrite)

1. Create Windows VPS; install MT5 + Poetry deps.  
2. Copy agent + `local.env` pattern (`QF_MT5_SLOT_ROOT` on VPS disk).  
3. Run `prepare-slots` / `supervise` under Scheduled Task.  
4. Point `QUANTFORG_API_BASE_URL` at Railway; keep token out of git.  
5. Do not expose agent ports publicly — outbound HTTPS only.

## Safety

- `MULTI_ACCOUNT_*` LIVE flags stay false  
- No real-money trades  
- Do not stop the LIVE Program Files terminal with worker scripts  
