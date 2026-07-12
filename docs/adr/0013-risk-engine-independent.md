# ADR-0013: Risk Engine Independent

## Status

Accepted

## Context

Risk limits protect capital and compliance. If risk checks live inside
strategies or broker adapters, they are inconsistently applied and easy to
bypass under “urgent” changes.

## Decision

QuantForg treats the **Risk Engine as an independent domain capability**.

Rules:

1. Risk evaluates proposed trading intentions against risk profiles, limits,
   exposure, and session constraints.
2. Risk does **not** depend on a specific strategy implementation or broker.
3. Execution adapters must only accept intentions that have passed risk
   approval (enforced in application orchestration).
4. Analysis engines do not call risk; risk does not perform market-structure
   analysis.
5. Risk configuration is explicit (`RiskProfile` and future limit aggregates),
   versioned, and auditable.
6. Fail-closed: if risk cannot evaluate, intentions are rejected.

Risk implementation may be incomplete today; independence is mandatory when
introduced.

## Consequences

**Positive**

- Single choke point for capital protection.
- Strategies remain replaceable without rewriting limits.
- Clear audit: who proposed vs who approved.

**Negative**

- Additional hop in the order path.
- Risk engine becomes critical path for availability (design for fail-closed).

**Neutral**

- Soft warnings vs hard rejects are policy inside risk, not in strategies.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Per-strategy risk copy-paste | Drift and bypass |
| Broker-side risk only | Too late; inconsistent across venues |
| Analysis-time risk that blocks snapshots | Mixes observation with capital policy |

## References

- ADR-0010 Analysis Never Trades
- ADR-0012 Strategy Is Plugin
- ADR-0014 MT5 Is Adapter
- [docs/domain.md](../domain.md) (RiskProfile)
