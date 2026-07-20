# RC1 — API

Base path: `/api/v1` (see app routers).

## Auth

- Bearer JWT (Supabase / app auth). Admin routes require owner/admin role.
- Auth endpoints are rate-limited (`AuthRateLimitMiddleware`).

## Operations (admin)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/ops/dashboard` | Ops dashboard aggregate |
| GET | `/ops/metrics` | Process metrics |
| GET | `/ops/alerts` | Server alerts |
| GET | `/ops/audit` | Audit center |
| GET | `/ops/rc1-telemetry` | RC1 live telemetry (audits + probes) |

## Execution audits

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/execution/audits` | User audit list |
| GET | `/execution/audits/{request_id}` | Immutable chain for one request |

## Health

| Method | Path |
| --- | --- |
| GET | `/health` |
| GET | `/health/detailed` (where enabled) |

Payload contracts must stay stable; extend with additive fields only.
