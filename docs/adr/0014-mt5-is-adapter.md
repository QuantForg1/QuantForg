# ADR-0014: MT5 Is Adapter

## Status

Accepted

## Context

MetaTrader 5 is a likely execution and market-data venue for QuantForg users.
Treating MT5 types, terminals, or Expert Advisor concepts as domain language
would couple the platform to a single vendor and break Clean Architecture.

## Decision

**MetaTrader 5 is an infrastructure adapter only.**

Rules:

1. No MT5 imports, bindings, or terminal assumptions in `domain` or
   `application` business rules.
2. MT5 connectivity implements ports such as market-data provider, order
   execution, or account sync — defined by QuantForg, not by MT5 APIs.
3. Mapping between MT5 payloads and domain types (Symbol, Order, Candle)
   lives in `infrastructure` (anti-corruption layer).
4. Analysis and strategies never call MT5 directly (ADR-0010, ADR-0012).
5. Failure of MT5 must surface as port errors; domain remains vendor-neutral.
6. Current sprints explicitly exclude MT5 implementation; this ADR constrains
   future work.

## Consequences

**Positive**

- Vendor replaceability (other brokers/venues behind the same ports).
- Testability without a running terminal.
- Domain language stays QuantForg-owned.

**Negative**

- Mapping layer effort for every MT5 quirk.
- Some MT5-only features may not map cleanly (document gaps; do not leak).

**Neutral**

- Demo/reference adapters may use in-memory fakes until MT5 is scheduled.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| MT5 as the domain model | Vendor lock-in; untestable core |
| EA scripts as primary architecture | Bypasses platform governance and risk |
| Shared MT5 DTOs in domain | Still couples ubiquitous language to vendor |

## References

- ADR-0001 Clean Architecture
- ADR-0006 Plugin Architecture
- ADR-0010 Analysis Never Trades
- [docs/architecture.md](../architecture.md)
