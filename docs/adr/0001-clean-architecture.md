# ADR-0001: Clean Architecture

## Status

Accepted

## Context

QuantForg is a long-lived trading platform that will accumulate market analysis,
risk, strategy, broker adapters, and AI advisory capabilities. Without strict
layering, framework and infrastructure choices leak into business rules,
making the system hard to test, replace, or reason about under regulatory and
operational pressure.

We need an architecture that:

- Keeps domain rules independent of FastAPI, SQLAlchemy, Redis, and brokers.
- Allows adapters (PostgreSQL today, MetaTrader later) to be swapped.
- Makes dependency direction enforceable in review and CI.

## Decision

QuantForg adopts **Clean Architecture** with inward-only dependencies:

```
presentation → application → domain ← infrastructure
                    ↑
                  core/
```

| Layer | Responsibility |
|---|---|
| `domain` | Entities, value objects, domain events, ports; Python stdlib only |
| `application` | Use cases, DTOs, orchestration over ports |
| `infrastructure` | Adapters implementing ports (DB, cache, brokers, clocks) |
| `presentation` | HTTP/API surface; no direct SQL/Redis |
| `core` | Cross-cutting config, logging, DI, security helpers |

Dependency rule: source code dependencies point **inward**. Outer layers may
depend on inner layers; never the reverse.

## Consequences

**Positive**

- Domain and analysis engines remain unit-testable without I/O.
- Broker and persistence technologies can change behind ports.
- Reviewers have a clear boundary checklist.

**Negative**

- More files and indirection for simple CRUD.
- Contributors must learn layer rules before shipping features.

**Neutral**

- `core/` is shared infrastructure utilities, not a business layer.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Framework-centric MVC (fat controllers + ORM models) | Couples business rules to FastAPI/SQLAlchemy |
| Hexagonal only without explicit application layer | Use-case orchestration becomes unclear as the platform grows |
| Modular monolith without ports | Harder to substitute MT5/AI later without rewriting callers |

## References

- [docs/architecture.md](../architecture.md)
- [Architecture Governance Guide](../architecture-governance.md)
- Uncle Bob — *Clean Architecture*
- ADR-0002 Domain Driven Design
- ADR-0006 Plugin Architecture
- ADR-0014 MT5 Is Adapter
