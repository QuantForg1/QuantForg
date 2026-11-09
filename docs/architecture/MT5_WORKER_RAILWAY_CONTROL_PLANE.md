# MT5 Worker ↔ Railway Control Plane (Phase 1C)

Stacked on PRs #207 → #208 → #209.

## Routes (all require `Authorization: Bearer <WORKER_SERVICE_TOKEN>`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/mt5-workers/hosts/register` | Idempotent host capacity registration |
| POST | `/api/v1/mt5-workers/register` | Idempotent worker registration per host slot |
| GET | `/api/v1/mt5-workers/assignments/{worker_id}` | Assignment view (no passwords) |
| POST | `/api/v1/mt5-workers/heartbeat` | Durable heartbeat + optional lifecycle hint |
| POST | `/api/v1/mt5-workers/health` | Host metrics (secrets stripped) |
| POST | `/api/v1/mt5-workers/release` | Stop / release worker |
| POST | `/api/v1/mt5-workers/revoke` | Revoke assignment; further access denied |
| POST | `/api/v1/mt5-workers/reconnect` | Safe reconnect with backoff |
| POST | `/api/v1/mt5-workers/stale/scan` | Mark heartbeat-stale workers |
| POST | `/api/v1/mt5-workers/credentials/authorize` | Assignment authorization only — **never returns password** |

## Security

- Bearer service token, constant-time compare.
- No public unauthenticated worker endpoints.
- Outbound HTTPS from Windows only.
- Passwords never logged or returned.
- Revoked workers cannot heartbeat or read assignments.
- `MULTI_ACCOUNT_*` LIVE flags remain **false**.

## Durability note

Control-plane state is **process-durable** on the Railway API instance (singleton on `app.state`). Schema tables from Phase 1B exist for future Postgres persistence; applying production migrations still requires owner approval.

## Local Windows agent

```powershell
$env:QUANTFORG_API_BASE_URL="https://quantforg-production.up.railway.app"
$env:WORKER_SERVICE_TOKEN="<same as Railway>"
poetry run python -m services.mt5_worker_agent.main railway-register
poetry run python -m services.mt5_worker_agent.main railway-heartbeat
```

Authenticated MT5 demo count remains **0** until `QF_DEMO_*` credentials succeed via `connect-demo`.

## Disk / RAM (this host)

After three portable slots: ~2 GB free disk, ~1.1 GB free RAM. Safe cleanup targets: `frontend/.next`, `frontend/node_modules/.cache`, pytest temp — **never** Program Files LIVE MT5 or `mt5_worker_slots` active data without operator intent.
