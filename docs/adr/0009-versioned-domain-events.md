# ADR-0009: Versioned Domain Events

## Status

Accepted

## Context

Domain events are a long-lived contract for consumers (projections, audits,
integration bridges). Renaming fields or changing semantics without version
discipline breaks subscribers and replay.

## Decision

QuantForg **versions domain events** as part of their public contract.

Rules:

1. Every event declares a stable `event_type` string
   (e.g. `liquidity.sweep_detected`).
2. Breaking payload changes require a **new event type** or an explicit
   version suffix / schema version field (e.g. `event_type` + `schema_version`).
3. Additive optional fields are allowed without a new type if consumers must
   tolerate absence (forward compatible).
4. Removing or reinterpreting fields is a breaking change → new type; old
   type remains until consumers migrate.
5. `to_dict()` serialisation is the canonical interop shape for buses and
   logs.
6. Event identity (`event_id`) and UTC `occurred_at` remain mandatory
   envelope fields.

Foundation events start at schema version **1** (implicit). When a version
field is introduced platform-wide, existing types default to `1`.

## Consequences

**Positive**

- Safe evolution of the event catalogue.
- Clear migration path for subscribers.
- Better auditability of historical payloads.

**Negative**

- Temporary dual-publish or dual-consume during migrations.
- Catalogue size grows with versions.

**Neutral**

- Integration events (ADR-0011) follow the same versioning discipline with
  their own namespace.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Unversioned evolving dict payloads | Silent consumer breakage |
| Only binary schema registry from day one | Heavy ops for current scale |
| Reuse same type with incompatible meaning | Corrupts replay and audits |

## References

- [docs/events-and-market-data.md](../events-and-market-data.md)
- ADR-0003 Event Driven Architecture
- ADR-0011 Domain Events vs Integration Events
