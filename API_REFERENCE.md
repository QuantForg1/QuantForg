# API Reference

**Release:** QuantForg v1.0.0-rc.1  
**Base path:** `/api/v1`  
**Machine-readable:** [`openapi/openapi.v1.0.0-rc1.json`](openapi/openapi.v1.0.0-rc1.json) (also `openapi/openapi.json`)

Interactive docs (non-production): `/docs`, `/redoc`, `/openapi.json`.

## Conventions

- JSON request/response bodies unless noted.  
- Auth endpoints issue session tokens via Supabase-backed flows.  
- Protected routes require authenticated session (see middleware).  
- **Live execution is disabled** unless `EXECUTION_ENABLED=true` (not for RC1).  

## Foundation

| Method | Path | Summary |
|--------|------|---------|
| GET | `/health` | Dependency health (Postgres, Redis); 503 if unhealthy |
| GET | `/health/ready` | Readiness probe |
| GET | `/health/live` | Liveness probe |
| GET | `/metrics` | Operational metrics snapshot |
| GET | `/version` | App name, version, environment |

## Authentication — `/auth`

| Method | Path | Summary |
|--------|------|---------|
| POST | `/auth/register` | Register |
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| POST | `/auth/refresh` | Refresh session |
| POST | `/auth/verify-email` | Verify email |
| POST | `/auth/forgot-password` | Start password reset |
| POST | `/auth/change-password` | Change password |
| GET | `/auth/oauth/{provider}` | OAuth redirect URL |
| POST | `/auth/oauth/callback` | OAuth callback |
| GET | `/auth/me` | Current user |

## User platform

| Prefix | Capabilities |
|--------|----------------|
| `/profile` | Get/patch profile, activity, avatar upload |
| `/settings` | User settings, devices, sessions, revoke |
| `/notifications` | List, mark read, preferences |
| `/organizations` | List/create orgs, invitations |

## Brokers

| Prefix | Capabilities |
|--------|----------------|
| `/brokers` | CRUD, health, diagnostics |
| `/broker-accounts` | User broker accounts CRUD |
| `/broker-connections` | Connections, connect/disconnect, validate |

## MT5 — `/mt5`

Status, connect/disconnect, account, symbols, ticks, candles, order validate/calculate.  
Does **not** place live trades in RC1.

## Execution — `/execution`

| Method | Path | Summary |
|--------|------|---------|
| POST | `/execution/check` | Safety decision |
| POST | `/execution/submit` | Submit path — blocked when execution disabled |

## Portfolio

`/portfolio`, `/positions`, `/positions/{ticket}`, `/orders`, `/orders/{ticket}`, `/history`

## Risk / Strategy / Simulation

| Prefix | Capabilities |
|--------|----------------|
| `/risk` | `POST /check` |
| `/strategy` | `POST /evaluate`, `GET /signals` |
| `/backtests` | `POST /run`, list, get by id |
| `/paper` | Orders, positions, history, performance |
| `/walkforward` | `POST /run`, results, get by id |

## Operations — `/ops`

| Method | Path | Summary |
|--------|------|---------|
| GET | `/ops/dashboard` | Monitoring dashboard |
| GET | `/ops/metrics` | Persisted-capable metrics view |
| GET | `/ops/alerts` | Alert rules + alerts |
| GET | `/ops/audit` | Audit Center buckets |

## OpenAPI generation

Regenerate after route changes:

```bash
poetry run python -c "..."  # or use the RC script path documented in RELEASE_CANDIDATE_v1_REPORT.md
```

The checked-in file under `openapi/` is authoritative for RC1.
