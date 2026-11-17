# Production worker supervisor: multi-user MT5 on the existing Windows host

This runs each customer's own MT5 account in an isolated portable terminal on the existing Windows host. It uses no new VPS and never touches the Weltrade LIVE terminal in Program Files.

## How a customer gets a robot (no developer involved)

1. The customer connects MT5 in Broker Accounts (broker, exact server, login, master password).
   - Since #341 this **only registers** the account; the shared platform terminal is never touched.
   - The server must match the broker.
   - An account already registered by another user is refused.
   - The password is stored AES-GCM encrypted in `broker_credentials`.
2. The backend gives the oldest waiting account a free slot. Each account gets its own slot and worker; nothing is shared.
   - `QF_AUTO_ASSIGN_ENVIRONMENTS` (Railway) controls which environments are assigned. The default is `demo`.
   - When every slot is busy, the account waits in the queue.
   - Owner and admin accounts are never assigned to a worker; they run on the platform terminal.
3. The supervisor claims a sealed envelope bound to that worker and unwraps it in memory. It then logs in on the slot's own terminal and reports redacted evidence.
4. READY follows MT5 `trade_allowed`:
   - An investor (read-only) login authenticates but stays **TRADING_PERMISSION_DISABLED**.
   - A slot that reports a login other than the assigned account is refused.
5. The Robot Control Center shows the verified connection state and the per-account Pause, Resume and Stop controls.
6. Before any order, the risk guard checks:
   - the account snapshot (9 / 25 / RR 1.5 / 0.45 / session / 1 position);
   - the owner-verified commission (`POST /api/v1/robot-control/admin/accounts/{id}/verified-commission`);
   - robot state.

   LIVE multi-account submit stays disabled behind `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED`.

## One-time setup on the Windows host (owner)

PowerShell, in the repo root on the host:

```powershell
Copy-Item deploy\mt5_worker_agent\local.production.env.example deploy\mt5_worker_agent\local.production.env
notepad deploy\mt5_worker_agent\local.production.env
#   QUANTFORG_API_BASE_URL=https://quantforg-production.up.railway.app
#   WORKER_SERVICE_TOKEN=<same value as Railway WORKER_SERVICE_TOKEN>
#   QF_MT5_SLOT_ROOT=C:\QuantForg-Workspace\mt5_worker_slots
#   QF_MT5_LOCAL_SLOTS=demo-a,demo-b
#   QF_MT5_MAX_CONCURRENT_PORTABLES=2
#   QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
.\deploy\mt5_worker_agent\protect_local_env.ps1
.\deploy\mt5_worker_agent\prepare_local_slots.ps1
.\deploy\mt5_worker_agent\start_production_supervisor.ps1
```

Each loop the supervisor:
- registers (or re-registers) every slot that is not ready;
- provisions assigned accounts;
- sends heartbeats.

Logs show `slot_rebound`, `slot_provision ... ready=... trade_allowed=...` and `local_supervisor_tick`.

## Capacity

The soft cap is 2 concurrent portable terminals (`QF_MT5_MAX_CONCURRENT_PORTABLES`). Before raising it, measure CPU, RAM and MT5 connection stability on the host with N terminals for 30 minutes. Record the result in the master tracker. Never claim unlimited capacity.

## Acceptance (DEMO only, no LIVE orders)

- Two different users connect DEMO accounts, and each gets a different slot (`user_id` and `broker_account_id` per worker).
- A wrong password gives REQUIRES_USER_ACTION. An investor password gives TRADING_PERMISSION_DISABLED.
- Pausing user A blocks only A's entries.
- A third account while 2 slots are busy is queued, and no session is shared.
- Kill a slot terminal: the heartbeat degrades, then the slot recovers.

## Startup verification (Claude, read-only, after the owner starts it)

| # | Evidence | Pass |
|---|---|---|
| 1 | `worker_hosts` / `mt5_workers` rows | 1 host, 2 slots registered, heartbeats under 45 s old |
| 2 | Railway `POST /mt5-workers/heartbeat` 200 | every ~15 s per slot |
| 3 | Robot Control Center (customer) | account shows "Assigned · online" only once its slot reports it |
| 4 | Owner account | never appears on a worker (assignment query excludes owner/admin) |
| 5 | Platform terminal | still Weltrade-Real 12439799; supervisor logs never mention it |
