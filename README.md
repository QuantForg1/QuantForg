# QuantForg

**AI-Powered Algorithmic Trading Platform**

Phase 1 foundation and Phase 2 analysis engines (Sprints 1–9).

> This repository contains the **platform skeleton** and **domain analysis engines**
> (market context, structure, liquidity, order blocks, fair value gaps).
> Live trading execution, MetaTrader integration, AI advisors, and strategy
> execution are **not implemented** and remain architecturally reserved.

---

## Stack

| Concern | Technology |
|---|---|
| Language | Python 3.13 |
| API | FastAPI |
| Packaging | Poetry |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2 (async) |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Containers | Docker / Compose |
| Quality | Ruff, Black, MyPy, Pytest |
| CI | GitHub Actions |

---

## Architecture

Clean Architecture with explicit layer boundaries:

```
presentation  →  application  →  domain  ←  infrastructure
                      ↑
                    core/
```

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Quick start

```bash
# 1. Bootstrap (Poetry, .env, pre-commit, Docker deps)
./scripts/bootstrap.sh

# 2. Run the API
make run

# 3. Verify
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/version
```

OpenAPI docs (development): http://localhost:8000/docs

---

## Folder mapping

Requested top-level concerns are organised under Clean Architecture packages:

| Requested | Location |
|---|---|
| `config/` | `core/config/` |
| `database/` | `core/database/` + `app/infrastructure/database/` |
| `security/` | `core/security/` |
| `logging/` | `core/logging/` |
| `api/` | `app/presentation/routers/` |
| `services/` | `app/application/services/` |
| `utils/` | `core/utils/` |

## Project structure

```
QuantForg/
├── app/                     # Clean Architecture application
│   ├── domain/              #   Entities, VOs, exceptions, ports
│   ├── application/         #   Use cases & DTOs
│   ├── infrastructure/      #   DB, cache, repositories
│   └── presentation/        #   Routers, middleware, dependencies
├── core/                    # Cross-cutting: config, logging, DI, security
├── alembic/                 # Database migrations
├── tests/                   # Unit & integration tests
├── docs/                    # Architecture & operations docs
├── scripts/                 # Bootstrap & utility scripts
├── docker/                  # Compose & Postgres init
├── .github/                 # CI workflows & PR template
├── pyproject.toml           # Poetry + tool configuration
├── Dockerfile               # Multi-stage production image
├── Makefile                 # Developer commands
└── .env.example             # Environment variable template
```

Every file is documented in [docs/file-reference.md](docs/file-reference.md).

---

## Foundation endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Readiness — probes PostgreSQL and Redis |
| `GET` | `/api/v1/health/live` | Liveness — process is running |
| `GET` | `/api/v1/version` | Application name, version, environment |

---

## Quality gates

```bash
make lint        # Ruff
make format      # Black + Ruff autofix
make typecheck   # MyPy strict
make test        # Pytest with coverage
make check       # lint + typecheck + test
make ci          # Full CI parity locally
```

---

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Layers, SOLID, dependency rules |
| [Architecture governance](docs/architecture-governance.md) | ADRs, non-negotiables, review process (Sprint 7.5) |
| [ADRs](docs/adr/README.md) | Architecture Decision Records (0001–0015) |
| [Engineering standards](docs/engineering/README.md) | DoD, reviews, testing, release, security |
| [Contributing](CONTRIBUTING.md) | Contributor workflow |
| [Changelog](CHANGELOG.md) | Keep a Changelog |
| [Domain model](docs/domain.md) | Entities, value objects, invariants (Sprint 2) |
| [Application layer](docs/application.md) | Use cases & DTOs (Sprint 3) |
| [Events & market data](docs/events-and-market-data.md) | Event bus & market-data foundation (Sprint 4) |
| [Market context](docs/market-context.md) | Session/calendar/regime engine (Sprint 5) |
| [Market structure](docs/market-structure.md) | Swings, BOS/CHoCH, trend (Sprint 6) |
| [Liquidity](docs/liquidity.md) | Equal highs/lows, pools, sweeps (Sprint 7) |
| [Order blocks](docs/order-block.md) | Order blocks, mitigation, breakers (Sprint 8) |
| [Fair value gaps](docs/fair-value-gap.md) | FVGs, fills, invalidation (Sprint 9) |
| [Configuration](docs/configuration.md) | Settings system and environments |
| [Development](docs/development.md) | Local workflow and conventions |
| [Deployment](docs/deployment.md) | Docker and production checklist |
| [File reference](docs/file-reference.md) | Explanation of every file |

---

## License

Proprietary — see [LICENSE](LICENSE).
