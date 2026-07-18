## Summary

<!-- What changed and why? Link issues/ADRs. -->

## Type of change

- [ ] Feature
- [ ] Bug fix
- [ ] Documentation / ADR / governance
- [ ] Tests
- [ ] Refactor
- [ ] Chore / CI / deps
- [ ] Breaking change (describe migration)

## Architecture impact

- [ ] No architecture impact
- [ ] Touches ports / layers / events / engines — completed
      [Architecture Review Checklist](../docs/engineering/ArchitectureReviewChecklist.md)
- [ ] New or updated ADR under `docs/adr/`

### Non-negotiable confirmations

- [ ] Analysis code does **not** trade or call execution (ADR-0010)
- [ ] No MT5 / vendor types in `domain/` (ADR-0014)
- [ ] No autonomous AI execution (ADR-0015)
- [ ] Dependencies point inward (ADR-0001)

## Design Bible (required for UI / product UX)

See [Design Bible](../docs/design/README.md) (ADR-0022).

- [ ] N/A — no product UI change
- [ ] Complies with Design Bible / UX Principles / Tokens / Typography
- [ ] [Component Acceptance](../docs/design/component-acceptance-checklist.md) completed (or N/A)
- [ ] [Feature Acceptance](../docs/design/feature-acceptance-checklist.md) completed (or N/A)
- [ ] Real data or empty states only (no production mocks)
- [ ] No live order submit outside Terminal
- [ ] Accessibility + performance budgets considered

## Checklist

- [ ] Follows [Definition of Done](../docs/engineering/DefinitionOfDone.md)
- [ ] [Code Review Checklist](../docs/engineering/CodeReviewChecklist.md) self-reviewed
- [ ] Tests added/updated (`make check` passes)
- [ ] Docs / CHANGELOG updated when needed
- [ ] Conventional commit messages used

## Test plan

<!-- Exact steps reviewers can follow -->

1.
2.

## Screenshots / notes

<!-- Optional — required for visual OS changes -->
