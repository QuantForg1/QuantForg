# Deployment Checklist

## Pre-deploy

- [ ] `main` is green for intended SHA
- [ ] Backend migrations reviewed (none required for this observability release)
- [ ] `NEXT_PUBLIC_API_BASE_URL` points at production API `/api/v1`
- [ ] `NEXT_PUBLIC_MOCK_AI=false`
- [ ] CORS allows production frontend origin
- [ ] Feature flags set intentionally (`NEXT_PUBLIC_FF_*`)
- [ ] Beta/maintenance/read-only flags set intentionally
- [ ] Optional webhooks configured and reachable
- [ ] `NEXT_PUBLIC_BUILD_VERSION` or Vercel git SHA available

## Frontend validation (local or CI)

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Backend validation

```bash
# from repo root — use project’s established test entrypoint
pytest -q
# or: python -m pytest
```

## Post-deploy smoke

- [ ] `/` loads; no hydration console errors
- [ ] Login / logout works
- [ ] `/ops` shows API health + version/environment
- [ ] Realtime status transitions when authenticated
- [ ] `/mt5` status loads (or gated if FF off)
- [ ] Feature-gated routes show empty state when flag off
- [ ] Feedback widget submits without console errors
- [ ] Submit a benign settings change; confirm client audit entry on Ops
- [ ] Trigger a known API 404; confirm monitored error includes `request_id`

## Closed beta go-live

- [ ] `NEXT_PUBLIC_BETA_MODE=true`
- [ ] Invite code distributed out-of-band
- [ ] Banner visible for unlocked beta users
- [ ] Maintenance mode verified once in staging (`NEXT_PUBLIC_MAINTENANCE_MODE=true` then off)

## Rollback trigger

Rollback if: auth broken, health red for >5 minutes after deploy, execution incorrectly enabled for beta cohort, or widespread client error spike on Ops.
