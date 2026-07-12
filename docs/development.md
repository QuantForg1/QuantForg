# Development Guide

## Prerequisites

- Python 3.13+
- Poetry 1.8+
- Docker & Docker Compose
- Make (optional but recommended)

## First-time setup

```bash
./scripts/bootstrap.sh
```

Or manually:

```bash
cp .env.example .env
poetry install
poetry run pre-commit install
make docker-up   # Postgres + Redis + API
```

## Common commands

| Command | Purpose |
|---|---|
| `make run` | Start API with hot reload |
| `make test` | Full test suite |
| `make test-unit` | Unit tests only |
| `make lint` | Ruff |
| `make format` | Black + Ruff fix |
| `make typecheck` | MyPy strict |
| `make check` | lint + typecheck + test |
| `make migrate` | Apply Alembic migrations |
| `make docker-up` | Start compose stack |

## Project layout (Clean Architecture)

```
app/
  domain/           entities, value objects, exceptions, ports
  application/      services (use cases), DTOs
  infrastructure/   repositories, database, cache
  presentation/     routers, middleware, dependencies, schemas
  main.py           FastAPI factory + lifespan
core/
  config/           Settings + environment factories
  database/         Engine / session manager
  di/               Dependency injection container
  logging/          Structured logging setup
  security/         Crypto helpers + security headers
  utils/            Identifiers, timing
```

## Conventions

- Clean Architecture + ADRs — see [Architecture Governance Guide](architecture-governance.md)
- Conventional Commits — see [CommitConvention.md](engineering/CommitConvention.md)
- Definition of Done — see [DefinitionOfDone.md](engineering/DefinitionOfDone.md)

## Adding a new use case (later sprints)

1. Define port in `app/domain/interfaces/`
2. Implement use case in `app/application/services/`
3. Add adapter in `app/infrastructure/`
4. Expose via router in `app/presentation/routers/`
5. Wire in `app/presentation/dependencies/`
6. Add tests under `tests/`

## API endpoints (foundation)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Readiness (Postgres + Redis) |
| `GET` | `/api/v1/health/live` | Liveness (process only) |
| `GET` | `/api/v1/version` | App name, version, environment |
| `GET` | `/docs` | OpenAPI UI (non-production) |
