# ADR-0007: Analysis Pipeline

## Status

Accepted

## Context

Market understanding is composed of ordered stages: context (session/
calendar), structure (swings/BOS/CHoCH), liquidity (equals/pools/sweeps), and
later optional enrichers. Ad-hoc calls between engines create cyclic
dependencies and non-reproducible results.

## Decision

QuantForg defines a unidirectional **analysis pipeline**:

```
Price history / market data
        ↓
Market Context Engine
        ↓
Market Structure Engine
        ↓
Liquidity Engine
        ↓
Order Block Engine
        ↓
Fair Value Gap Engine
        ↓
(Future enrichers via ports — never execution)
        ↓
MarketAnalysisSnapshot (ADR-0008)
```

Rules:

1. Each stage is a pure(ish) domain engine behind ports; no trading side
   effects (ADR-0010).
2. Stages consume immutable inputs and emit immutable snapshots + domain
   events.
3. Later stages may read earlier snapshots via ports; earlier stages must
   not depend on later ones.
4. Pipeline orchestration lives in application layer (or a dedicated
   orchestrator), not inside individual engines.
5. Stages are independently testable with fakes.

## Consequences

**Positive**

- Reproducible, ordered analysis.
- Clear ownership per sprint/engine.
- Easy to skip or stub stages in tests.

**Negative**

- End-to-end latency is the sum of stages (mitigate with caching of
  snapshots).
- Orchestrator must handle partial failure policy explicitly.

**Neutral**

- Parallelism within a stage is allowed; cross-stage parallel fan-out is
  only allowed when data dependencies permit.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Single “god” analyser | Untestable and unreviewable |
| Event-only choreography without ordered stages | Harder reproducibility for analysis |
| Strategies owning their own full analysis | Duplicates logic; violates ADR-0012 boundary |

## References

- [docs/market-context.md](../market-context.md)
- [docs/market-structure.md](../market-structure.md)
- [docs/liquidity.md](../liquidity.md)
- [docs/order-block.md](../order-block.md)
- [docs/fair-value-gap.md](../fair-value-gap.md)
- ADR-0008 MarketAnalysisSnapshot
- ADR-0010 Analysis Never Trades
