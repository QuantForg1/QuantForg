# ADR-0010: Analysis Never Trades

## Status

Accepted

## Context

Analysis engines (context, structure, liquidity, future enrichers) interpret
markets. If they can place or mutate orders, a bug in swing detection becomes
a capital event. Regulatory and operational separation of “observe” vs “act”
is mandatory for a production trading platform.

## Decision

**Analysis never trades.**

Hard rules:

1. Analysis packages must not call execution ports, broker adapters, or order
   aggregates’ mutating APIs.
2. Analysis must not generate **trade signals** or entry/exit instructions.
   Structure facts (BOS, sweep) are observations, not orders.
3. Pipeline outputs are snapshots + domain events only (ADR-0007, ADR-0008).
4. Any future path from insight → order must go:
   `Analysis → (optional AI advice) → Strategy plugin → Risk engine → Execution`
   with explicit application orchestration.
5. Code review and architecture review must reject PRs that import execution
   concerns into analysis modules.
6. Tests for analysis use fakes for price/swing ports only — never live
   brokers.

## Consequences

**Positive**

- Blast radius of analysis bugs is informational, not financial.
- Clear mental model for contributors.
- Enables aggressive iteration on analysis without execution risk.

**Negative**

- Extra orchestration layer before any automated trading exists.
- Temptation to “just send one order from the engine” must be refused.

**Neutral**

- Recording signal *metadata* for audit (Sprint 3 style) is not execution;
  live order placement remains forbidden here.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Engines emit orders directly for “speed” | Catastrophic coupling and risk |
| Analysis emits soft signals consumed as orders | Blurs observation vs decision; still unsafe |
| Feature-flag execution inside engines | Flags fail; boundaries must be structural |

## References

- ADR-0007 Analysis Pipeline
- ADR-0012 Strategy Is Plugin
- ADR-0013 Risk Engine Independent
- ADR-0015 AI Is Advisor
- [Definition of Done](../engineering/DefinitionOfDone.md)
