# QuantForg MT5 Worker Agent (Phase 1B)

Deployable **Windows** agent that will own **one** isolated MetaTrader 5
terminal session per QuantForg user account.

## Critical facts

| Claim | Status |
| --- | --- |
| Agent code / scripts in repo | Yes (this folder) |
| Runs on Railway | **No** — Railway is Linux; `terminal64.exe` requires Windows |
| Auto-provisions cloud VMs | **No** — owner must approve and create Windows hosts |
| Actual MT5 sessions running from this PR | **0** unless an operator installs on a host |
| Replaces Weltrade LIVE singleton | **No** |

## Architecture split

```text
Railway (Linux API)          Windows worker host(s)
  control plane  <-------->  worker agent + terminal64
  encrypted secrets store      decrypt only in-memory for login
  never runs MT5               one terminal slot per user worker
```

Existing production Weltrade path (`deploy/mt5_gateway`) remains the LIVE
singleton. Multi-user workers stay behind feature flags.

## Host requirements (per concurrent user slot)

- Windows Server / Windows 10+ VM with GUI or Auto-Logon capable session
- Dedicated portable MT5 data directory per worker slot (recommended)
- Python 3.13 + MetaTrader5 package
- Outbound HTTPS to QuantForg API (service identity token)
- Cloudflare Tunnel or private network — **do not** expose agent ports publicly

Rough sizing (planning only, not measured): ~1–2 GB RAM and 1 vCPU per
active terminal slot; start with 4–8 slots/host and measure before scaling.

## Operator steps (external — not performed by this PR)

1. Obtain owner approval for a Windows VPS/VM budget.
2. Install MT5 + agent dependencies.
3. Register host capacity in control plane (`worker_hosts`).
4. Configure `WORKER_SERVICE_TOKEN` (never commit).
5. Run `.\start_worker_agent.ps1` under a supervised Scheduled Task.
6. Execute `docs/architecture/MT5_WORKER_INTEGRATION_TEST.md` on demo accounts.

## Local dry-run (no real MT5)

Use `MockMt5WorkerAgent` in unit tests. That mock is **not** a real session.
