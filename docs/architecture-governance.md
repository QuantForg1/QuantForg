# Architecture Governance Guide

This guide defines how QuantForg makes, records, and enforces architectural
decisions. It is **process and documentation only** — it does not implement
trading, AI, MetaTrader, strategies, indicators, or execution.

## Purpose

- Keep Clean Architecture and DDD boundaries intact as the platform grows.
- Separate **analysis** from **decision** from **risk** from **execution**.
- Make irreversible decisions explicit via ADRs.
- Give reviewers shared checklists and a clear Definition of Done.

## Pillars

| Pillar | Binding ADR(s) |
|---|---|
| Clean Architecture | [ADR-0001](adr/0001-clean-architecture.md) |
| Domain-Driven Design | [ADR-0002](adr/0002-domain-driven-design.md) |
| Event-driven communication | [ADR-0003](adr/0003-event-driven-architecture.md), [ADR-0011](adr/0011-domain-events-vs-integration-events.md) |
| UTC + Decimal correctness | [ADR-0004](adr/0004-utc-everywhere.md), [ADR-0005](adr/0005-decimal-only.md) |
| Plugins | [ADR-0006](adr/0006-plugin-architecture.md) |
| Analysis pipeline & snapshots | [ADR-0007](adr/0007-analysis-pipeline.md), [ADR-0008](adr/0008-market-analysis-snapshot.md) |
| Versioned events | [ADR-0009](adr/0009-versioned-domain-events.md) |
| Analysis never trades | [ADR-0010](adr/0010-analysis-never-trades.md) |
| Strategy / Risk / MT5 / AI roles | [ADR-0012](adr/0012-strategy-is-plugin.md)–[ADR-0015](adr/0015-ai-is-advisor.md) |

## Non-negotiables

1. **Dependencies point inward.** Domain does not import frameworks or vendors.
2. **Analysis never trades.** No orders from context/structure/liquidity engines.
3. **AI advises; it does not execute.**
4. **MT5 is an adapter**, never the domain model.
5. **Strategies are plugins**; intentions pass **independent risk** before execution.
6. **UTC everywhere** for instants; **Decimal only** for prices and money.
7. **ADRs are append-only.** Deprecate or supersede; do not delete history.

## How to change architecture

```
1. Identify the force / problem
2. Draft ADR (status: Proposed)
3. Open PR with label architecture
4. Complete Architecture Review Checklist
5. Merge → status Accepted
6. Update docs/architecture.md and indexes if behaviour/process changed
```

Lightweight changes that fit existing ADRs do not need a new ADR; reference
the governing ADR in the PR instead.

## Review & ownership

- Code changes: [CodeReviewChecklist.md](engineering/CodeReviewChecklist.md)
- Architecture changes: [ArchitectureReviewChecklist.md](engineering/ArchitectureReviewChecklist.md)
- Merge rights: see root `CODEOWNERS`
- Done means: [DefinitionOfDone.md](engineering/DefinitionOfDone.md)

## Documentation map

| Area | Location |
|---|---|
| ADRs | [docs/adr/](adr/README.md) |
| Engineering policies | [docs/engineering/](engineering/README.md) |
| Layer architecture | [docs/architecture.md](architecture.md) |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) |
| Security | [docs/engineering/SecurityPolicy.md](engineering/SecurityPolicy.md) |

## Enforcement

Governance is enforced by:

- Human review (checklists + CODEOWNERS)
- CI quality gates (`make check`)
- Explicit sprint rules (no trading/AI/MT5/execution in analysis sprints)
- Future optional lint/import-linter rules aligned to ADR-0001

Violations block merge unless an ADR explicitly supersedes the prior rule.
