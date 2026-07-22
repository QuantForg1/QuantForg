# QuantForg v1.0.0 — Architecture Guide

**Audience:** operators and engineers maintaining long-running institutional deployments.  
**Scope:** existing architecture only — no new modules.

## Runtime path

```
Browser (Next.js desks)
  → Railway API (FastAPI /api/v1)
      → Windows MT5 Gateway (HTTP / WS)
          → MetaTrader 5 → Weltrade
  ↘ Supabase Postgres (audits, RLS, durable OMS/risk state)
```

Cloudflare Tunnel fronts the Windows gateway hostname. Peak equity / daily PnL HWM also persist under `.quantforg_state/` (and Postgres migration when applied).

## Layers (unchanged)

| Layer | Responsibility |
| --- | --- |
| Presentation | FastAPI routers, Next.js desks |
| Application | Use cases (validate → risk → safety → submit) |
| Domain | Policies, entities — no I/O |
| Infrastructure | Postgres, Redis, MT5 gateway client, probes |

## Eight primary surfaces

Terminal · Book · Research · Counsel · Journal · Broker · Inbox · Settings

Ops / Monitoring / Incidents are operator surfaces — not a ninth product desk and not a second AI.

## Execution spine (fail-closed)

1. Validation  
2. Risk  
3. Safety  
4. Submit (MT5 `order_send` only when `EXECUTION_ENABLED` + live gateway)  

Prefer No Trade. Never invent fills, equity, or ticks.

## Health & alerts

| Endpoint | Role |
| --- | --- |
| `GET /api/v1/health/live` | Process alive |
| `GET /api/v1/health/ready` | Dependencies |
| `GET /api/v1/ite/ops/services-health` | Per-service status / latency / last error + production alerts |
| `GET /api/v1/ite/ops/control-center` | Mode, kill switch, readiness |
| `GET /api/v1/ite/reliability/*` | Continuous health, incidents, recovery |

Alert kinds include gateway offline, MT5 disconnect / login expired, high spread, no ticks, high latency, execution timeout, risk/safety lock, high drawdown, memory/disk, database, calendar.

## Related docs

- [Operations Guide](./OPERATIONS_GUIDE.md)  
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)  
- [Recovery Guide](./RECOVERY_GUIDE.md)  
- [Production Review](./PRODUCTION_REVIEW.md)  
- ADR-0016–0022, Design Bible `docs/design/`  
