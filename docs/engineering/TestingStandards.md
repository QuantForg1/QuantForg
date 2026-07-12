# Testing Standards

## Goals

- Protect domain invariants and analysis correctness.
- Keep tests fast, deterministic, and free of real brokers/AI/MT5.
- Encode architecture rules: ports + fakes, not hidden I/O.

## Test layers

| Layer | Location | May use | Must not |
|---|---|---|---|
| Unit | `tests/unit/` | Domain, fakes, in-memory ports | Network, DB, Redis, Docker |
| Integration | `tests/integration/` | Testcontainers / compose deps | Live MT5, paid AI APIs |
| API / e2e | `tests/e2e/` (when present) | Running app + fakes/stubs | Production credentials |

Mark tests with pytest markers (`unit`, `integration`, …) consistently with
`pyproject.toml`.

## Domain & analysis rules

1. Prefer **Arrange–Act–Assert** with explicit fixtures.
2. Build candles/prices via factories (`Decimal`/`str`, never `float`).
3. Time: inject clocks or pass `as_of`; freeze time in fakes.
4. Assert on business facts (roles, sweep kind, snapshot fields), not
   incidental UUIDs unless identity is deterministic by design.
5. Analysis tests must not import execution, strategy, or MT5 modules.

## Fakes vs mocks

- **Fakes** (in-memory ports) are preferred for repositories and price series.
- **Mocks** are acceptable for interaction-focused application tests; avoid
  over-mocking domain logic.

## Coverage expectations

- New domain behaviour: unit tests required.
- New ports: at least one fake + consumer test.
- Bug fixes: regression test required.
- Docs-only / ADR-only: no code tests required.

## CI

- `make test` / `make check` must pass before merge.
- Do not skip failing tests; fix or quarantine with an issue link and marker.
- Flaky tests are defects — quarantine immediately.

## Forbidden

- `time.sleep` for synchronisation in unit tests.
- Hitting the public internet in unit tests.
- Committing credentials for third-party trading or AI services.
- Deleting assertions to greenwash CI.
