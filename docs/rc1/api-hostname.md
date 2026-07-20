# API hostname — Railway is canonical

**Decision (V1.0):** Outcome **B** — custom hostname `api.quantforg.com` is **intentionally retired**.

## Diagnosis (verified 2026-07-20)

| Probe | Result |
| --- | --- |
| DNS `api.quantforg.com` (8.8.8.8 / 1.1.1.1) | NXDOMAIN |
| `curl https://api.quantforg.com/health` | curl exit 6 — could not resolve host |
| `https://quantforg-production.up.railway.app/api/v1/health` | HTTP 200 |
| `www.quantforg.com` | Resolves to Vercel (frontend) |

## Canonical API endpoint

- https://quantforg-production.up.railway.app
- https://quantforg-production.up.railway.app/api/v1
- https://quantforg-production.up.railway.app/health

Frontend: `NEXT_PUBLIC_API_BASE_URL=https://quantforg-production.up.railway.app/api/v1`

## Policy

Do not treat `api.quantforg.com` as a production dependency. Smoke scripts and ops docs use the Railway public domain.
