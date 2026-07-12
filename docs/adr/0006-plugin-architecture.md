# ADR-0006: Plugin Architecture

## Status

Accepted

## Context

QuantForg will grow strategies, broker connectors, AI advisors, notification
channels, and analysis extensions. Baking each capability into the core
application creates a monolith that cannot be released or tested
independently and violates the open/closed principle.

## Decision

QuantForg adopts a **plugin architecture** for extensible capabilities:

1. Core platform defines **ports** and stable contracts in `domain` /
   `application`.
2. Plugins are separately versioned modules that implement those ports.
3. Discovery and wiring happen in composition root / DI (`core/di`), never
   inside domain entities.
4. First-class plugin categories (future or present):
   - Strategy plugins (ADR-0012)
   - Broker / venue adapters (ADR-0014)
   - AI advisor plugins (ADR-0015)
   - Optional analysis enrichers behind ports
5. Plugins **must not** bypass risk (ADR-0013) or execute trades from
   analysis (ADR-0010).

A plugin declares metadata (name, version, capabilities) and is enabled via
configuration, not hard-coded imports in domain code.

## Consequences

**Positive**

- Independent evolution and testing of extensions.
- Clear security boundary: untrusted logic stays behind ports.
- Core remains releasable without every strategy present.

**Negative**

- Requires disciplined versioning of plugin contracts.
- Misconfigured plugins can fail at startup (acceptable vs silent coupling).

**Neutral**

- In-repo packages may act as “built-in plugins” during early sprints while
  still obeying port boundaries.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Monolithic feature flags inside core | Still couples release cadence |
| Dynamic `importlib` with no contracts | Unsafe and untyped |
| Microservices per strategy from day one | Operational cost too high early |

## References

- ADR-0001 Clean Architecture
- ADR-0012 Strategy Is Plugin
- ADR-0014 MT5 Is Adapter
- ADR-0015 AI Is Advisor
- [Architecture Governance Guide](../architecture-governance.md)
