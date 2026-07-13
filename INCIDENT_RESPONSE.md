# Incident Response

## Severity

| Level | Example | Response |
|---|---|---|
| SEV1 | Trading impossible for all users; auth outage; data corruption risk | Immediate page; freeze deploys; maintenance mode |
| SEV2 | MT5 or execution degraded; elevated API errors | Investigate within 15m; consider read-only mode |
| SEV3 | Single-region latency; non-critical feature flag off | Business hours |
| SEV4 | Cosmetic / feedback only | Backlog |

## First 5 minutes

1. Open `/ops` (privileged account).
2. Note **API health**, **Database**, **Redis**, **Queue**, **MT5**, **Realtime**, **Version**, **Environment**.
3. Capture recent client errors (Ops → Recent errors) and server alerts if available.
4. Confirm latest deploy SHA on Vercel + Railway matches expected `main`.
5. If unsafe: set `NEXT_PUBLIC_MAINTENANCE_MODE=true` or `NEXT_PUBLIC_READ_ONLY_MODE=true` and redeploy frontend (or use edge config if configured).

## Classification

| Symptom | Likely layer |
|---|---|
| Login fails for all | Auth / Supabase / CORS |
| Health 5xx | Railway API process / DB |
| Ops dashboard 403 only | RBAC (not an outage) |
| MT5 only failing | Broker terminal / MT5 bridge |
| Realtime offline, API ok | Client engine / network / auth session |
| Orders rejected in UI with read-only banner | Intentional read-only mode |

## Communication

- Use feedback webhook / support channel for beta users.
- Do not ask users for passwords; rotate credentials server-side if leaked.
- Record timeline: detect → mitigate → resolve → postmortem.

## Rollback

1. Frontend: redeploy previous Vercel deployment.
2. Backend: Railway rollback to last known-good image/SHA.
3. Feature flags: disable `mt5` / `paper` / `workspace` / `ai` via env or localStorage override for operators validating mitigations.
4. Re-enable only after `/health` green and smoke tests pass.

## Post-incident

- Attach error `request_id`s from Ops recent errors.
- Update `INCIDENT_RESPONSE.md` only if process gaps found.
- File follow-ups; do not silently change API contracts during hotfixes unless required for safety.
