# Code Review Checklist

Use this checklist for every pull request. Reviewers should verify items;
authors should self-check before requesting review.

## Intent & scope

- [ ] PR title/summary match the actual diff.
- [ ] Scope is focused; unrelated refactors are separated.
- [ ] Linked issue/ADR exists for non-trivial changes.

## Architecture

- [ ] Dependencies point inward (ADR-0001).
- [ ] Domain has no FastAPI / SQLAlchemy / Redis / MT5 / HTTP clients.
- [ ] New I/O goes behind ports; fakes exist for tests.
- [ ] Analysis never trades or emits execution orders (ADR-0010).
- [ ] Strategies/AI/MT5 (if touched) obey ADR-0012 / 0014 / 0015.

## Correctness

- [ ] Invariants enforced in domain (`require`, VOs), not only in UI.
- [ ] UTC-aware datetimes; no naive “assumed UTC” silently.
- [ ] Prices/quantities use `Decimal` / VOs; no `float` money paths.
- [ ] Error types are appropriate (validation vs conflict vs not found).

## Tests

- [ ] Unit tests cover new behaviour and edge cases.
- [ ] Tests are deterministic (no real network/clock flakiness).
- [ ] Negatives: invalid input and boundary conditions asserted.

## Quality

- [ ] Names match ubiquitous language.
- [ ] No dead code, commented-out blocks, or debug prints.
- [ ] Logging has no secrets; appropriate levels used.
- [ ] Public APIs and events documented when changed.

## Security

- [ ] No credential leakage; `.env` not committed.
- [ ] AuthZ/AuthN changes reviewed for least privilege.
- [ ] User input validated at boundaries.

## Docs & release

- [ ] Docs / ADR / CHANGELOG updated as needed.
- [ ] Feature flags or migrations called out in the PR body.

## Frontend / Trading OS (when UI touched)

- [ ] Complies with [Design Bible](../design/README.md) (ADR-0022).
- [ ] [Component Acceptance](../design/component-acceptance-checklist.md) for new/redesigned components.
- [ ] [Feature Acceptance](../design/feature-acceptance-checklist.md) for product features.
- [ ] Real data or empty states — no production mocks / fabricated metrics.
- [ ] No new primary nav beyond the eight surfaces without ADR.
- [ ] Counsel / Research / Book do not submit live orders; Terminal remains execution.
- [ ] Tokens / typography / a11y / performance budgets respected.

## Reviewer decision

- [ ] Approve / request changes with concrete feedback.
- [ ] Blocking issues labelled clearly vs nits.
