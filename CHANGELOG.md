# Changelog

All notable changes to QuantForg are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/)
(see [docs/engineering/VersioningPolicy.md](docs/engineering/VersioningPolicy.md)).

## [Unreleased]

### Added

- MT5 Gateway session attach: `POST /session/attach` reuses an already
  logged-in Windows terminal without collecting the broker password;
  optional `MT5_GATEWAY_AUTO_ATTACH` for local DX; `symbol_select` before
  quotes/candles; `deploy/mt5_gateway/gateway.env.example`.
- Closed Beta onboarding: Get Started hub, first-run checklist, product tour,
  broker connection wizard, paper trading tutorial, in-app What’s New,
  and beta docs (`BETA_ONBOARDING.md`, `BETA_OPERATIONS.md`,
  `BETA_FEEDBACK_PLAN.md`, `BETA_CHECKLIST.md`).

## [1.0.0] - 2026-07-12

### Added

- General Availability packaging: version `1.0.0`, OpenAPI `openapi/openapi.v1.0.0.json`,
  `GA_READINESS_REPORT.md`, migration verify scripts.
- Durable Postgres Unit of Work factories for all feature modules
  (platform, broker, MT5, execution, portfolio, risk, strategy, backtest,
  paper, walk-forward, ops), selected via `DURABLE_PERSISTENCE` / non-testing env.
- Committed `poetry.lock` for reproducible installs.

### Safety

- `EXECUTION_ENABLED` remains **false** by default.
- No AI features.
- No new trading features beyond prior RC1 surface.

### Changed

- Promote package/app version from `1.0.0-rc.1` to `1.0.0`.
- CI dependency cache keyed on `poetry.lock`.

## [1.0.0-rc.1] - 2026-07-12

### Added

- Release Candidate packaging: version `1.0.0-rc.1`, OpenAPI export (`openapi/`),
  and release documentation set (`ARCHITECTURE.md`, `DEPLOYMENT.md`,
  `OPERATIONS.md`, `SECURITY.md`, `BACKUP_RECOVERY.md`, `API_REFERENCE.md`,
  `PRODUCTION_READINESS_REPORT.md`, `RELEASE_CANDIDATE_v1_REPORT.md`).
- Operations & Observability Platform: monitoring dashboard, metrics collector,
  alerting (info/warning/critical), Audit Center, health ready probe,
  `/api/v1/metrics`, ops migrations + RLS.
- Walk-Forward Validation Engine (IS/OOS, robustness, promotion decisions).
- Paper Trading Engine (virtual broker, positions, performance).
- Backtesting Engine with metrics.
- Strategy Runtime (evaluate + signals; no live send).
- Risk Engine (`POST /risk/check`).
- Portfolio / Position Engine (read/sync paths).
- Execution Safety + Execution Gateway (submit gated by `EXECUTION_ENABLED`).
- MT5 Adapter sprints 1–4 (connect, market data, validation, portfolio, gateway).
- Broker Foundation (brokers, accounts, connections, health/reconnect).
- Authentication and User Platform (profiles, settings, orgs, notifications).
- Supabase SQL foundation with reversible migrations and RLS.

### Safety

- `EXECUTION_ENABLED` remains **false** by default.
- No AI features in this release candidate.
- No new live trading features beyond existing gated execution path.

### Changed

- Package/app version bumped from `0.1.0` to `1.0.0-rc.1`.
- Dockerfile base image aligned to Python **3.13** (matches CI / `pyproject.toml`).
- Development status classifier moved Alpha → Beta.

## [0.1.0] - 2026-07-12

### Added

- Fair Value Gap Engine (Sprint 9): 3-candle FVGs, fills, invalidation, quality.
- Order Block Engine (Sprint 8): zones, lifecycle, mitigation, breakers, quality.
- Architecture governance (Sprint 7.5): ADRs 0001–0015, engineering policies,
  contributing guide, changelog, CODEOWNERS, issue and PR templates.
- Market Structure Engine (Sprint 6): swings, BOS/CHoCH, trend snapshots.
- Liquidity Engine (Sprint 7): equal highs/lows, pools, zones, sweeps.
- Market Context Engine (Sprint 5): sessions, calendar, liquidity/volatility profiles.
- Event bus and market-data foundation (Sprint 4).
- Application use cases and ports (Sprint 3).
- Domain model foundation (Sprint 2).
- Platform skeleton: FastAPI, Poetry, Docker, CI, health/version (Sprint 1).

### Changed

- Documentation indexes now include ADRs, engineering standards, and
  architecture governance.
