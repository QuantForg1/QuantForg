# ADR-0008: MarketAnalysisSnapshot

## Status

Accepted

## Context

Consumers (future strategies, risk, UI, AI advisors) need a coherent,
point-in-time view of analysis outputs. Passing live mutable engines or
partial tuples invites race conditions and inconsistent reads.

## Decision

QuantForg standardises on **immutable analysis snapshots** as the read model
between pipeline stages and downstream consumers.

1. Each engine already produces a typed immutable snapshot
   (`StructureSnapshot`, `LiquiditySnapshot`, context aggregates/records).
2. A composite **`MarketAnalysisSnapshot`** (application or domain read
   model) aggregates per-symbol/timeframe analysis for a given `as_of` UTC
   instant:
   - market context summary
   - structure snapshot (optional if stage skipped)
   - liquidity snapshot (optional if stage skipped)
   - schema/version metadata
3. Snapshots use Decimal prices and UTC timestamps (ADR-0004, ADR-0005).
4. Snapshots are append-only from the consumer’s perspective; updates create
   new snapshot identities.
5. Persistence of snapshots goes through repository ports (no SQL in domain).

Until the composite type is implemented, individual engine snapshots remain
the source of truth; the composite is the mandated integration shape.

## Consequences

**Positive**

- Deterministic inputs for strategies and advisors.
- Auditable “what did we know at time T?”
- Natural cache and replay unit.

**Negative**

- Storage growth if every tick persists full composites (mitigate with
  policies and retention).
- Schema evolution requires versioning (align with ADR-0009).

**Neutral**

- Engines may continue to return stage-local snapshots; composition is an
  orchestration concern.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Live query of mutable engine state | Non-reproducible; threading hazards |
| Only event log replay for reads | Higher complexity for synchronous consumers |
| Mutable shared “market brain” object | Violates immutability and Clean Architecture |

## References

- ADR-0004 UTC Everywhere
- ADR-0005 Decimal Only
- ADR-0007 Analysis Pipeline
- ADR-0009 Versioned Domain Events
- [docs/market-structure.md](../market-structure.md)
- [docs/liquidity.md](../liquidity.md)
