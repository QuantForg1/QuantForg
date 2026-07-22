# Operations Runbook

Institutional operator procedures for QuantForg **v1.0.0**.

Canonical runbook steps also live in
`app/domain/institutional_trading/operations/runbooks.py` and
`docs/production/OPERATIONS_GUIDE.md`.

## Quick paths

| Action | Runbook id / doc |
|---|---|
| Startup | `startup` |
| Shutdown | `shutdown` |
| Restart | `restart` |
| Gateway reconnect | `gateway_restart` / `mt5_reconnect` |
| Broker failure | `broker_failure` |
| Emergency stop | `emergency_shutdown` + Auto Trading emergency-stop API |
| Disaster recovery | `disaster_recovery` + `BACKUP_RECOVERY.md` |
| Incident response | `incident_response` |

Execute via `POST /api/v1/ite/ops/runbooks/{id}/execute` (OWNER/ADMIN).

## Surfaces

| Surface | Purpose |
|---|---|
| `/ops` | Operator dashboard: API/DB/Redis/queue, realtime, MT5, latency, version, flags, recent errors/audit |
| `/monitoring` | Live gateway / broker health |
| `/incidents` | Reliability incidents (`/ite/reliability/incidents`) |
| `GET /health` | Public liveness + dependency probes |
| `GET /health/live` | Process alive |
| `GET /ite/ops/services-health` | Per-service heartbeat / latency / alerts |
| `GET /ite/ops/control-center` | Mode, kill switch, readiness |
| `GET /ops/dashboard` | Privileged component health |
| `GET /ops/metrics` | Latency / error rate / throughput |
| `GET /ops/alerts` | Server alerts (owner/admin) |
| `GET /ops/audit` | Server audit trail (owner/admin) |
| Browser localStorage | `qf.ops.errors.v1`, `qf.ops.audit.v1`, feedback store |

## Feature flags

Env (build-time defaults):

- `NEXT_PUBLIC_FF_AI`
- `NEXT_PUBLIC_FF_MT5`
- `NEXT_PUBLIC_FF_PAPER`
- `NEXT_PUBLIC_FF_WORKSPACE`
- `NEXT_PUBLIC_FF_BETA` (off unless `true`)

Runtime override (no redeploy):

```js
localStorage.setItem("qf.ff.overrides.v1", JSON.stringify({ ai: false, mt5: true }))
location.reload()
```

Clear overrides: `localStorage.removeItem("qf.ff.overrides.v1")`.

## Beta / maintenance

| Variable | Effect |
|---|---|
| `NEXT_PUBLIC_BETA_MODE=true` | Require invite unlock |
| `BETA_INVITE_CODE` | Server-only invite (never `NEXT_PUBLIC_BETA_INVITE_CODE`) |
| `NEXT_PUBLIC_MAINTENANCE_MODE=true` | Block app behind maintenance gate |
| `NEXT_PUBLIC_READ_ONLY_MODE=true` | Block mutating trading actions in UI |

Unlock key: `qf.beta.unlocked.v1`.

## Webhooks (optional)

| Variable | Payload |
|---|---|
| `NEXT_PUBLIC_ERROR_WEBHOOK_URL` | Sanitized monitored errors |
| `NEXT_PUBLIC_AUDIT_WEBHOOK_URL` | Sanitized client audit events |
| `NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL` | Bug / feature / general feedback + browser info |

## Common checks

1. **API down:** `/ops` shows health error → check Railway service + domain + CORS.
2. **Realtime offline:** Confirm user authenticated; RealtimeEngine uses polling fallback — offline means engine stopped or network blocked.
3. **MT5 disconnected:** Expected when no terminal session; treat `error` status as probe failure.
4. **Redis disabled:** Normal on tiers without Redis; queue may show `—`.
5. **Ops 401/403:** Expected for non-admin users on privileged ops endpoints; health still works.
6. **Desk disagreement:** If Auto Trading ≠ Broker ≠ Monitoring gateway state — Prefer No Trade and open `/ite/ops/services-health`.

## Soak & backup

```bash
python scripts/institutional_soak.py --profile stress
python scripts/backup_production_state.py
python scripts/config_audit.py
```

## Client diagnostics

From browser console (authenticated session):

```js
JSON.parse(localStorage.getItem("qf.ops.errors.v1") || "[]")
JSON.parse(localStorage.getItem("qf.ops.audit.v1") || "[]")
```

## Do not

- Log passwords, tokens, or MT5 credentials.
- Disable RealtimeEngine or replace with fake WS frames.
- Change `/api/v1` contracts to “fix” ops issues.
- Invent ticks, fills, equity, or calendar events.
