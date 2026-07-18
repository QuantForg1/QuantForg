# Architecture Decision Records

Architecture Decision Records (ADRs) capture significant QuantForg design
choices using the [Michael Nygard ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Format

Every ADR includes:

| Section | Purpose |
|---|---|
| **Title** | Numbered, imperative decision name |
| **Status** | Proposed · Accepted · Deprecated · Superseded |
| **Context** | Forces and constraints that drove the decision |
| **Decision** | What we chose |
| **Consequences** | Positive, negative, and neutral outcomes |
| **Alternatives Considered** | Options rejected and why |
| **References** | Related ADRs, docs, and external sources |

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-clean-architecture.md) | Clean Architecture | Accepted |
| [0002](0002-domain-driven-design.md) | Domain Driven Design | Accepted |
| [0003](0003-event-driven-architecture.md) | Event Driven Architecture | Accepted |
| [0004](0004-utc-everywhere.md) | UTC Everywhere | Accepted |
| [0005](0005-decimal-only.md) | Decimal Only | Accepted |
| [0006](0006-plugin-architecture.md) | Plugin Architecture | Accepted |
| [0007](0007-analysis-pipeline.md) | Analysis Pipeline | Accepted |
| [0008](0008-market-analysis-snapshot.md) | MarketAnalysisSnapshot | Accepted |
| [0009](0009-versioned-domain-events.md) | Versioned Domain Events | Accepted |
| [0010](0010-analysis-never-trades.md) | Analysis Never Trades | Accepted |
| [0011](0011-domain-events-vs-integration-events.md) | Domain Events vs Integration Events | Accepted |
| [0012](0012-strategy-is-plugin.md) | Strategy Is Plugin | Accepted |
| [0013](0013-risk-engine-independent.md) | Risk Engine Independent | Accepted |
| [0014](0014-mt5-is-adapter.md) | MT5 Is Adapter | Accepted |
| [0015](0015-ai-is-advisor.md) | AI Is Advisor | Accepted |
| [0016](0016-trading-os-information-architecture.md) | Trading OS Information Architecture | Accepted |
| [0017](0017-continuously-releasable-frontend-baseline.md) | Continuously Releasable Frontend Baseline | Accepted |
| [0018](0018-terminal-os-flagship-shell.md) | Terminal OS Flagship Shell | Accepted |
| [0019](0019-book-os-portfolio-operating-system.md) | Book OS Portfolio Operating System | Accepted |
| [0020](0020-research-os-workflow-shell.md) | Research OS Workflow Shell | Accepted |
| [0021](0021-counsel-os-decision-operating-system.md) | Counsel OS Decision Operating System | Accepted |
| [0022](0022-design-bible-and-product-governance.md) | Design Bible and Product Governance | Accepted |

## Process

1. Propose a new ADR when a decision is irreversible, cross-cutting, or
   contested.
2. Number sequentially (`NNNN-kebab-title.md`).
3. Open a PR labelled `architecture`; complete the
   [Architecture Review Checklist](../engineering/ArchitectureReviewChecklist.md).
4. Once merged, status is **Accepted** unless explicitly marked otherwise.
5. Never delete ADRs — mark **Deprecated** or **Superseded by ADR-XXXX**.

See the [Architecture Governance Guide](../architecture-governance.md).
