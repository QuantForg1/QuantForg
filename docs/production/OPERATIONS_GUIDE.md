# QuantForg v1.0.0 — Operations Guide

## Daily posture

1. Prefer No Trade when any desk disagrees.  
2. Monitoring, Broker, and Auto Trading must show the same gateway / MT5 facts.  
3. Acknowledge critical alerts before enabling Auto Trading.  
4. Kill switch armed ⇒ no new risk.

## Startup

Use runbook id `startup` (`GET /ite/ops/runbooks` → `POST .../startup/execute`):

1. Confirm `EXECUTION_ENABLED` intentional.  
2. Start API; probe `/health/live`.  
3. Start Windows MT5 Gateway; probe gateway `/health`.  
4. Attach / login MT5; confirm connected.  
5. Confirm Cloudflare tunnel reachable from API.  
6. Open Monitoring + Broker — identical state.  
7. Review `/ite/ops/control-center` mode (SHADOW until promoted).  
8. Ack overnight alerts.

## Shutdown / restart / emergency

| Runbook id | Use when |
| --- | --- |
| `shutdown` | Planned stop |
| `restart` | Controlled bounce |
| `emergency_shutdown` | Immediate halt |
| `gateway_restart` / `mt5_reconnect` | Connectivity only |
| `broker_failure` | Weltrade / broker outage |
| `recovery` / `disaster_recovery` | Post-incident / DR |
| `incident_response` | Active incident |

Also: `OPERATIONS_RUNBOOK.md` (legacy ops flags) and built-in `RUNBOOKS` in `app/domain/institutional_trading/operations/runbooks.py`.

## Health monitoring

Poll `GET /ite/ops/services-health` (OWNER/ADMIN). Each service reports:

- status · uptime · heartbeat · latency · last successful operation · last error · reconnect count  

Degradation raises deduped ops alerts (acknowledge via `/ite/ops/alerts/ack`).

## Production alerts (operator action)

| Alert | First action |
| --- | --- |
| Gateway disconnected | Arm kill; restart gateway; verify tunnel |
| MT5 login expired | Re-login terminal; do not invent session |
| High spread / no ticks | Prefer No Trade; check symbol_select |
| High latency / execution timeout | Halt Auto Trading; check gateway RTT |
| Risk / safety lock | Leave locked until root cause cleared |
| High drawdown | Keep kill armed; review peak equity file/DB |
| Memory / disk | Scale / free disk; capture soak report |
| Database unavailable | Fail closed; restore per Recovery Guide |
| Calendar unavailable | Advisory only — do not invent events |

## Soak / stability

```bash
python scripts/institutional_soak.py --profile stress
python scripts/institutional_soak.py --profile 24h --wall-seconds 30
# Dedicated host (do not claim complete until wall clock finishes):
# --wall-seconds 86400 | 259200 | 604800
```

Reports: `docs/production/reports/soak_*.json`.

## Backups

```bash
python scripts/backup_production_state.py
```

Plus Postgres `pg_dump` / Supabase PITR — see `BACKUP_RECOVERY.md`.

## Do not

- Invent ticks, fills, equity, or calendar events.  
- Bypass Risk / Safety / Decision.  
- Expose `BETA_INVITE_CODE` as `NEXT_PUBLIC_*`.  
- Disarm kill switch while Broker ≠ Monitoring.  
