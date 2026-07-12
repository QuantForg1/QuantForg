# ADR-0002: Domain Driven Design

## Status

Accepted

## Context

Trading and market-analysis concepts (orders, sessions, swings, liquidity
pools, risk profiles) are rich and invariant-heavy. Anemic DTOs scattered
across layers invite duplicated validation and inconsistent terminology.

We need a shared ubiquitous language and explicit domain building blocks so
product, engineering, and future strategy authors speak the same vocabulary.

## Decision

QuantForg applies **Domain-Driven Design (DDD)** building blocks where they
add clarity:

| Building block | Usage in QuantForg |
|---|---|
| Entities / aggregates | Identity + invariants (e.g. `User`, `TradingSession`) |
| Value objects | `Money`, `Price`, `SymbolCode`, immutable market records |
| Domain events | Facts that occurred inside the domain |
| Ports (repository / service interfaces) | Boundaries for persistence and external systems |
| Domain services | Pure analysis engines (structure, liquidity, context) |
| Application services / use cases | Orchestration across ports |

Ubiquitous language is documented in `docs/domain.md` and package docstrings.
Bounded contexts are expressed as packages (`market_data`, `market_context`,
`market_structure`, `liquidity`, …) rather than a single mega-model.

## Consequences

**Positive**

- Invariants live next to the data they protect.
- New contexts can evolve without rewriting unrelated models.
- ADRs and PR reviews can refer to named domain concepts.

**Negative**

- Learning curve for contributors unfamiliar with DDD.
- Risk of over-modelling trivial CRUD if discipline slips.

**Neutral**

- Not every table row is an aggregate; prefer VOs and records when identity
  is unnecessary.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Transaction-script services + anemic models | Validation and language fragment across layers |
| Event sourcing as default persistence | Premature complexity for foundation and analysis engines |
| Single shared “god” domain package | Contexts blur; merge conflicts and coupling explode |

## References

- [docs/domain.md](../domain.md)
- Eric Evans — *Domain-Driven Design*
- ADR-0001 Clean Architecture
- ADR-0003 Event Driven Architecture
- ADR-0009 Versioned Domain Events
