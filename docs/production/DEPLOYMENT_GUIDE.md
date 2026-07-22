# QuantForg v1.0.0 — Deployment Guide

## Components

| Component | Host | Notes |
| --- | --- | --- |
| API | Railway (or equivalent) | FastAPI, `APP_ENV=production` |
| Frontend | Vercel / Railway static | Next.js production build |
| Postgres | Supabase | Migrations under `supabase/migrations/` |
| MT5 Gateway | Windows host | `deploy/mt5_gateway/` |
| Tunnel | Cloudflare | Public hostname → gateway |

## Pre-flight

1. Secrets in platform secret store (never git).  
2. `SECRET_KEY` ≥ 32 chars; rotate from defaults.  
3. `EXECUTION_ENABLED=false` until OWNER intentionally enables after launch locks PASS  
   (Demo Certification is optional — see [LAUNCH_POLICY_DEMO_CERT_OPTIONAL.md](./LAUNCH_POLICY_DEMO_CERT_OPTIONAL.md)).  
4. `MT5_GATEWAY_BASE_URL` + `MT5_GATEWAY_CALLER_TOKEN` match gateway.  
5. `BETA_INVITE_CODE` server-only if `BETA_MODE=true`.  
6. Apply migrations including `live_account_risk_state` if using durable HWM.  
7. Config audit: `python scripts/config_audit.py`.

## Deploy sequence

1. Deploy API image tagged `1.0.0`.  
2. Run / verify migrations.  
3. Deploy frontend against API base URL.  
4. Start MT5 Gateway + tunnel.  
5. Probe `/api/v1/health/live` then `/ready`.  
6. OWNER: `/ite/ops/services-health` green or expected offline.  
7. Keep mode **SHADOW**; Auto Trading off.

## Rollback

1. Redeploy previous image tag.  
2. Schema: downs in `supabase/migrations/down/` (export data first).  
3. Keep `EXECUTION_ENABLED=false` during rollback.  

See `BACKUP_RECOVERY.md` and [Recovery Guide](./RECOVERY_GUIDE.md).

## Quality gate (release)

```bash
ruff check app core services tests
pytest -q
# integration suite as configured in CI
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Checklist

See [Production Checklist](./PRODUCTION_CHECKLIST.md).  
