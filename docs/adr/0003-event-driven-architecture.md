# ADR-0003: Event Driven Architecture

## Status

Accepted

## Context

Market analysis, session lifecycle, and future risk/strategy components need
to react to facts (candle closed, structure changed, liquidity swept) without
tight call-graph coupling. Synchronous fan-out from producers to every
consumer does not scale organisationally or technically.

## Decision

QuantForg adopts an **event-driven** style inside the platform:

1. Domain components emit **immutable domain events** when facts occur.
2. An **in-process event bus** (ports + foundation adapter) delivers events
   to subscribers in the same process for the foundation phase.
3. Producers must not know concrete consumers; they publish via
   `EventPublisherPort` / `EventBusPort`.
4. Cross-process / cross-service messaging uses **integration events**
   (see ADR-0011), not raw domain events.

Analysis engines return pending events alongside snapshots; application or
infrastructure layers publish them.

## Consequences

**Positive**

- Loose coupling between analysis, persistence, and future notifications.
- Auditable timeline of domain facts.
- Clear extension point for logging, metrics, and later message brokers.

**Negative**

- Ordering and idempotency must be designed deliberately.
- Debugging flows requires following events as well as call stacks.

**Neutral**

- Foundation uses in-process delivery only; broker-backed transport is an
  adapter decision, not a domain change.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Direct method calls between engines | Creates brittle dependency webs |
| Database triggers as the event system | Opaque, hard to test, infra-coupled |
| Full message bus from day one | Operational overhead before multi-service need |

## References

- [docs/events-and-market-data.md](../events-and-market-data.md)
- ADR-0009 Versioned Domain Events
- ADR-0011 Domain Events vs Integration Events
- Fowler — *What do you mean by “Event-Driven”?*
