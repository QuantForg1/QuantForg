# ADR-0005: Decimal Only

## Status

Accepted

## Context

Market prices, quantities, spreads, and money amounts require exact
representation. IEEE-754 `float` introduces rounding errors that compound in
comparisons (equal highs, BOS levels, risk limits) and are unacceptable for
financial correctness.

## Decision

**Monetary and price quantities use `decimal.Decimal` exclusively.**

Rules:

1. Domain value objects (`Price`, `Money`, quantities) wrap `Decimal`.
2. Construction from `float` is rejected at validation boundaries.
3. Prefer `str` or `int` or `Decimal` inputs in factories (`Price.of`,
   `Candle.create`).
4. Serialisation uses decimal strings (not binary floats) in events and
   snapshots.
5. Analysis engines compare `Decimal` values; never cast to `float` for
   structural logic.

## Consequences

**Positive**

- Exact equality and ordering for structure/liquidity logic.
- Safer audit and regulatory posture.
- Consistent serialisation across APIs and events.

**Negative**

- Slightly more verbose arithmetic.
- Interop with libraries that assume `float` needs explicit conversion at
  the absolute edge (and must be justified).

**Neutral**

- Non-financial metrics (latency ms, cache hit ratios) may use native ints
  or floats where exact decimal semantics are irrelevant.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| `float` throughout | Rounding bugs in equal-level and risk maths |
| Fixed-point integers only | Awkward for multi-asset precision differences |
| `numpy` float64 for analysis | Same float hazards; pulls scientific stack into domain |

## References

- [docs/domain.md](../domain.md)
- Python `decimal` module
- ADR-0002 Domain Driven Design
- ADR-0008 MarketAnalysisSnapshot
