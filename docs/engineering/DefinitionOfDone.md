# Definition of Done

A change is **done** only when all applicable criteria below are met.

## Universal

- [ ] Intent is clear in the PR description (what / why).
- [ ] Code compiles and `make check` passes (lint, typecheck, tests).
- [ ] No secrets, credentials, or personal data committed.
- [ ] Documentation updated when behaviour, APIs, or architecture change.
- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes.
- [ ] Follows [CodingStandards.md](CodingStandards.md) and Clean Architecture
      (ADR-0001).

## Domain / analysis changes

- [ ] Decimal prices and UTC timestamps respected (ADR-0004, ADR-0005).
- [ ] Snapshots/events remain immutable where required.
- [ ] Analysis modules do not trade, signal entries, or call execution
      (ADR-0010).
- [ ] Unit tests with fakes cover happy path and invariants.
- [ ] Multi-symbol / multi-timeframe readiness preserved where applicable.

## Architecture / ADR changes

- [ ] New or updated ADR follows Nygard sections.
- [ ] [ArchitectureReviewChecklist.md](ArchitectureReviewChecklist.md)
      completed.
- [ ] Superseded ADRs marked, never deleted.

## API / ops changes

- [ ] Backward compatibility considered; breaking changes documented.
- [ ] Migrations (if any) are forward-only and reviewed.
- [ ] Observability: logs/metrics/errors remain actionable.

## Frontend / Trading OS changes

- [ ] Follows [Design Bible](../design/README.md) (ADR-0022).
- [ ] [Feature Acceptance](../design/feature-acceptance-checklist.md) completed when shipping product UX.
- [ ] New components passed [Component Acceptance](../design/component-acceptance-checklist.md).
- [ ] `frontend` typecheck / lint / build expectations met (ADR-0017).
- [ ] No fabricated trading data; empty states when unavailable.
- [ ] Locked OS trees (`terminal/`, `book/`, `research/`, `counsel/`) only changed with explicit intent.

## Explicitly not done if

- Trading, MT5, AI execution, or strategy logic appears in analysis PRs
  without an accepted ADR exception.
- Tests were deleted to make CI green.
- Review checklist items were unchecked without justification.
- UI ships neon/gradient debt, mock balances, or execution outside Terminal.
