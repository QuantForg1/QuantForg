# ADR-0011: Domain Events vs Integration Events

## Status

Accepted

## Context

Not every domain fact should cross process or organisational boundaries.
Conflating internal domain events with external messages leaks ubiquitous
language, couples consumers to internal refactors, and complicates security.

## Decision

QuantForg distinguishes **domain events** from **integration events**.

| | Domain events | Integration events |
|---|---|---|
| Purpose | Facts inside the domain model | Contracts with other processes/systems |
| Lifetime | In-process bus, audits, projections | Message bus, webhooks, partner APIs |
| Shape | Rich domain vocabulary | Stable, often anti-corruption DTO |
| Ownership | Domain package | Application/infrastructure mapping |
| Versioning | ADR-0009 | ADR-0009 in a separate namespace |

Rules:

1. Domain engines emit domain events only.
2. Outbound integration publishes happen in application/infrastructure via
   explicit mappers (domain event → integration event).
3. External inbound messages are translated into commands/use cases or domain
   events at the edge — never deserialized straight into entities.
4. Naming: domain `liquidity.sweep_detected`; integration e.g.
   `quantforg.liquidity.sweep.v1`.

## Consequences

**Positive**

- Internal refactors do not break external contracts.
- Security and PII filtering at the mapping boundary.
- Clear ownership of stability guarantees.

**Negative**

- Mapping code to maintain.
- Dual catalogues to document.

**Neutral**

- Foundation may only implement domain events; integration catalogue grows
  when multi-service needs appear.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Publish domain events unchanged externally | Leaky, brittle contracts |
| No domain events — only integration | Domain loses rich internal signalling |
| Shared database as integration | Hidden coupling; violates ports |

## References

- ADR-0003 Event Driven Architecture
- ADR-0009 Versioned Domain Events
- Vernon — *Implementing Domain-Driven Design* (messaging boundaries)
