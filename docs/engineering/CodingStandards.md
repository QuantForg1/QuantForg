# Coding Standards

## Language & tooling

- Python **3.13+**
- Formatting: **Black**
- Lint: **Ruff**
- Types: **MyPy strict** (project configuration in `pyproject.toml`)
- Tests: **Pytest**
- Packaging: **Poetry**

Run `make check` before pushing.

## Architecture

- Obey Clean Architecture (ADR-0001) and DDD building blocks (ADR-0002).
- Domain: no frameworks, I/O, MT5, or AI SDKs.
- Prefer ports + adapters over concrete singletons.
- Analysis never trades (ADR-0010).

## Style

1. Explicit over clever; readable names from ubiquitous language.
2. Immutable domain records (`frozen` dataclasses) for snapshots/events.
3. `Decimal` for prices/money; reject `float` (ADR-0005).
4. Timezone-aware **UTC** instants (ADR-0004).
5. Narrow functions; one reason to change per module.
6. Docstrings on public domain types explaining **why they exist**.
7. No bare `except:`; catch specific exceptions.
8. No `print` debugging in committed code; use structured logging.

## Imports & packages

- Absolute imports from `app.` / `core.`.
- Avoid circular imports; invert via ports if needed.
- `__all__` for public package surfaces.

## Comments

- Comment **why**, not what.
- Prefer deleting obsolete comments over leaving TODOs without tickets.
- ADR references welcome for non-obvious constraints.

## Forbidden patterns

- Business rules in FastAPI routers or SQLAlchemy models.
- `float` in market maths.
- Naive datetimes in domain events/snapshots.
- Execution calls from analysis packages.
- Committed secrets or `.env` files with real credentials.
