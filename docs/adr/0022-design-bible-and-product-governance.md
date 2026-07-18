# ADR-0022: Design Bible and Product Governance

## Status

Accepted

## Context

Phases P0–P4 established Terminal, Book, Research, and Counsel as production
OS desks. Without permanent product governance, future features will reintroduce
duplication, visual drift, mock data, and competitor-clone UX.

## Decision

**QuantForg adopts a binding Design Bible and product governance suite.**

Location: `docs/design/`.

| Document | Binding role |
|---|---|
| Design Bible (`README.md`) | Constitution |
| Product Governance | Sacred surfaces & decision rights |
| Feature Lifecycle | Idea → ship → retire |
| UX Principles | Interaction law |
| Design Tokens | Visual tokens ↔ `globals.css` |
| Typography | IBM Plex system |
| Accessibility | WCAG 2.2 AA target |
| Performance Budgets | Speed & weight |
| Component Acceptance | New UI gate |
| Feature Acceptance | New feature gate |

### Enforcement

1. Human: PR template + Code Review + Definition of Done  
2. Agents: `.cursor/rules/quantforg-design-bible.mdc`  
3. CI: governance docs presence check (non-functional; prevents doc deletion)

### Explicit non-goals of this ADR

- No production runtime behavior change  
- No backend contract change  
- No redesign of P1–P4 shells in this change set  

## Consequences

**Positive** — Multi-year consistency; shared acceptance language; safer scaling.

**Negative** — Slightly higher PR ceremony for UI work.

## Alternatives Considered

1. **Informal taste only** — rejected; drifts under multiple contributors.  
2. **Heavy Storybook/visual regression in this phase** — deferred; docs first.

## References

- ADR-0016–0021 (OS desks)  
- ADR-0017 (releasable baseline)  
- `docs/design/README.md`
