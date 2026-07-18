# ADR-0019: Book OS Portfolio Operating System

## Status

Accepted

## Context

Dashboard, portfolio, analytics, performance, risk, risk-lab, and wallet
duplicated portfolio understanding across scrolling pages. Traders need one
Book surface to decide what to do next — not a KPI collage.

Terminal OS (ADR-0018) must not be modified.

## Decision

**`/book` renders `BookShell` — a zero-scroll portfolio operating system.**

### Merged into Book

Dashboard · Portfolio · Analytics · Performance · Risk · Risk Lab · Wallet
(legacy routes continue to redirect to `/book`).

### Original surfaces

| Component | Role | Data |
|---|---|---|
| Portfolio Health | Book viability | Live portfolio / session |
| Equity Timeline | Equity path | Deal reconstruction only |
| Risk DNA | Risk fingerprint | `portfolio-intelligence` + margin |
| Exposure Map | Capital map | Positions + optional sectors |
| Position Intelligence | Ranked open risk | Live positions → Terminal |
| Portfolio Counsel | Advisory strip | Live metrics + PI (never invents) |

### Rules

1. No mock balances, charts, or PnL.
2. Unavailable intelligence fields render `n/a` / empty — never fabricated.
3. Full-bleed chrome via AppShell (`/book` with Terminal).
4. Keyboard: 1–5 focus · C counsel · R refresh · ?

## Consequences

**Positive** — One portfolio OS; clear next action into Terminal.

**Negative** — Legacy dashboard module remains in repo until deleted in a later cleanup; not routed.

## References

- ADR-0016, ADR-0017, ADR-0018
- `frontend/src/components/book/shell.tsx`
