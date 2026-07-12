# Architecture Review Checklist

Required for PRs that change layer boundaries, ports, events, ADRs, DI wiring,
or introduce new bounded contexts / engines / adapters.

## Decision hygiene

- [ ] Problem statement is clear; forces documented.
- [ ] ADR opened or updated when the decision is significant (see
      [docs/adr/README.md](../adr/README.md)).
- [ ] Alternatives considered; rejection rationale recorded.
- [ ] Status and supersession links are correct.

## Boundary integrity

- [ ] Clean Architecture dependency rule holds (ADR-0001).
- [ ] New ports are narrow and intention-revealing (ISP).
- [ ] Adapters live in infrastructure; domain remains pure.
- [ ] No vendor types (MT5, LLM SDKs) in domain (ADR-0014, ADR-0015).

## Analysis & execution separation

- [ ] Analysis pipeline direction preserved (ADR-0007).
- [ ] Snapshots immutable; Decimal + UTC (ADR-0004, ADR-0005, ADR-0008).
- [ ] Analysis cannot trade (ADR-0010).
- [ ] Strategy/risk/execution paths remain distinct (ADR-0012, ADR-0013).

## Events

- [ ] Domain vs integration event boundary respected (ADR-0011).
- [ ] Event types versioned; breaking changes use new types (ADR-0009).
- [ ] Envelope fields (`event_id`, `occurred_at`) intact.

## Operability

- [ ] Failure modes and fail-closed behaviour defined where capital is near.
- [ ] Observability hooks considered (logs/metrics/traces).
- [ ] Migration / rollout / rollback notes present for breaking changes.

## Security & compliance posture

- [ ] Secrets and PII not embedded in events or snapshots unnecessarily.
- [ ] Plugin trust boundary documented if new plugins are introduced
      (ADR-0006).

## Sign-off

- [ ] Architecture-aware reviewer approval (see CODEOWNERS).
- [ ] Docs index / governance guide updated if process changed.
