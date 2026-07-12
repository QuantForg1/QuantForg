# ADR-0012: Strategy Is Plugin

## Status

Accepted

## Context

Trading strategies will proliferate and change faster than the platform core.
Embedding strategies in domain or analysis packages would force core releases
for every alpha tweak and violate analysis/execution separation.

## Decision

**Every strategy is a plugin** (ADR-0006).

Rules:

1. Strategies implement a stable port (e.g. `StrategyPort`) defined by the
   platform — they do not own persistence, brokers, or risk.
2. Strategy inputs are immutable analysis snapshots / approved DTOs
   (ADR-0008), never live engine handles.
3. Strategy outputs are **intentions** (proposed orders / adjustments), not
   executed trades.
4. All intentions pass through the **Risk Engine** (ADR-0013) before
   execution adapters.
5. Strategies must not import MT5, SQL, FastAPI, or analysis engine internals.
6. Strategy packages are optionally loadable; core boots without any strategy
   enabled.

Strategies are out of scope for current analysis sprints; this ADR binds
future work.

## Consequences

**Positive**

- Independent release and testing of alphas.
- Core remains stable while research iterates.
- Enforced risk gate before capital moves.

**Negative**

- Contract design must anticipate versioning early.
- Poorly written plugins can still propose unsafe intentions (risk must
  catch them).

**Neutral**

- Reference/example strategies may live in-repo under a `plugins/` or
  `strategies/` tree while obeying the same ports.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Strategies as core domain services | Couples research to platform releases |
| Strategies call brokers directly | Bypasses risk; violates ADR-0010/0013/0014 |
| Strategies embedded in analysis engines | Analysis must never trade (ADR-0010) |

## References

- ADR-0006 Plugin Architecture
- ADR-0008 MarketAnalysisSnapshot
- ADR-0010 Analysis Never Trades
- ADR-0013 Risk Engine Independent
