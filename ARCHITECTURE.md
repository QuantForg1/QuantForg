# Architecture

**Product:** QuantForg  
**Release:** v1.0.0-rc.1  
**Style:** Clean Architecture + Domain-Driven Design  

## Principles

- Dependency rule: domain ← application ← infrastructure / presentation  
- Supabase is the system of record for identity and SQL schema  
- MT5 is an adapter, never the domain core (ADR-0014)  
- Analysis never trades (ADR-0010)  
- Risk engine is independent (ADR-0013)  
- AI is advisor-only and **not shipped in RC1** (ADR-0015)  
- `EXECUTION_ENABLED` defaults to **false**; live `order_send` is gated  

## Layer map

```
presentation/   FastAPI routers, schemas, middleware, dependencies
application/    use cases, DTOs, application services
domain/         entities, value objects, enums, events, ports
infrastructure/ MT5, Supabase, Redis, SQLAlchemy, memory UoWs
core/           settings, DI container, logging, security, DB session
```

## Completed modules (RC1)

| Module | Responsibility |
|--------|----------------|
| Auth + User Platform | Register/login/OAuth, profiles, orgs, notifications |
| Broker Foundation | Brokers, accounts, connections, health/reconnect |
| MT5 Adapter | Connect, market data, validation, portfolio read, gated gateway |
| Execution Safety | Policy checks; submit blocked unless execution enabled |
| Portfolio Engine | Positions, orders, history sync (read path) |
| Risk Engine | Pre-trade risk assessment |
| Strategy Runtime | Signal evaluation (no live send) |
| Backtesting | Historical simulation |
| Paper Trading | Virtual broker fills |
| Walk-Forward | IS/OOS validation + promotion decision |
| Operations | Health, metrics, dashboard, alerts, audit center |

## Runtime wiring

`core/di/container.py` starts Postgres + Redis, registers Mock MT5 by default, and wires feature services. Most feature aggregates use in-memory Unit of Work factories for local/CI; identity can use Supabase when configured. SQL migrations under `supabase/migrations/` define the durable schema and RLS.

## API surface

All routes hang under `settings.api_prefix` (default `/api/v1`). OpenAPI: `openapi/openapi.v1.0.0-rc1.json`.

## Explicit non-goals for RC1

- Enabling live execution  
- Shipping AI features  
- New trading strategies beyond existing runtime/backtest/paper stack  

See also: `docs/architecture.md`, `docs/adr/`.
