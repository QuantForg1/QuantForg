# Architecture

QuantForg follows **Clean Architecture** with Domain-Driven Design building blocks
where they add clarity. Dependencies point **inward only**.

```
┌─────────────────────────────────────────────────────────────┐
│  presentation/     FastAPI routers, middleware, schemas     │
├─────────────────────────────────────────────────────────────┤
│  application/      Use cases, DTOs, orchestration           │
├─────────────────────────────────────────────────────────────┤
│  domain/           Entities, value objects, ports, errors   │
├─────────────────────────────────────────────────────────────┤
│  infrastructure/   SQLAlchemy, Redis, repository adapters   │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ depends on
┌────────┴────────┐
│  core/          │  Cross-cutting: config, logging, DI, security
└─────────────────┘
```

## Layer responsibilities

| Layer | May depend on | Must not |
|---|---|---|
| `domain` | Python stdlib only | Frameworks, DB, HTTP |
| `application` | `domain`, `core.config` (settings types) | FastAPI, SQLAlchemy, Redis clients |
| `infrastructure` | `domain` ports, `core`, SQLAlchemy, Redis | Presentation / HTTP |
| `presentation` | `application`, `domain` exceptions, `core` | SQL / Redis directly |
| `core` | Pydantic, SQLAlchemy engine helpers | Business rules |

## SOLID mapping

- **S** — Each module has one reason to change (e.g. `HealthService` only aggregates probes).
- **O** — New probes implement `HealthCheckPort` without modifying `HealthService`.
- **L** — Adapters are substitutable for their ports.
- **I** — Ports are narrow (`HealthCheckPort`, `RepositoryPort`, `UnitOfWorkPort`).
- **D** — Application depends on ports; infrastructure provides adapters.

## Foundation sprint scope

This sprint delivers the production skeleton only:

- Configuration, logging, DI, Docker, CI
- Health and version endpoints
- Database / Redis connection lifecycle
- Domain base types and exception hierarchy
- Alembic baseline

**Explicitly out of scope for foundation analysis work:** trading logic,
MetaTrader domain coupling, AI execution, indicators-as-signals, strategies
inside analysis engines, dashboards.

## Governance

Architectural rules are binding via ADRs and engineering policy:

- [Architecture Governance Guide](architecture-governance.md)
- [ADR index](adr/README.md)
- [Engineering standards](engineering/README.md)

Non-negotiables include Clean Architecture dependency direction, UTC + Decimal
correctness, analysis-never-trades, MT5-as-adapter, and AI-as-advisor.
