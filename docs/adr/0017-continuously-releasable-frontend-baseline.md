# ADR-0017: Continuously Releasable Frontend Baseline

## Status

Accepted

## Context

Phase P0 of the QuantForg Trading OS redesign established a clean TypeScript
baseline (`tsc --noEmit` passes). Further redesign work must not leave the
repository in a non-shippable state. Production trading depends on preserved
backend contracts, auth, and MT5 execution.

## Decision

**Every phase ends releasable. The clean `tsc` baseline is non-negotiable.**

### Hard preserves (never regress)

1. Production functionality
2. MT5 order execution path
3. Backend API / websocket / Supabase contracts
4. Authentication

### Frontend OS priorities (in order)

5. Remove mock/demo UI (real data or empty states only)
6. Collapse duplicate workflows
7. Eight primary surfaces only (ADR-0016)
8. Institutional design system (IBM Plex, steel tokens)
9. Terminal as flagship
10. Continuously releasable repo

### Pre-commit / pre-merge gate

Before every commit that touches the frontend (and for GitHub Actions on PRs):

| Check | Requirement |
|---|---|
| TypeScript | `tsc --noEmit` — zero errors; never weaken types to pass |
| ESLint | Clean |
| Build | Production build succeeds |
| Unit tests | Pass |
| CI | GitHub Actions green |

Do not introduce new TypeScript errors. Do not reduce type safety. Do not
proceed to the next redesign phase until the current phase is production-ready.

### Phase discipline

- **P0 (current baseline):** IA collapse, tokens/typography, Terminal home,
  mock/demo kill paths, SessionBar, ADR-0016/0017, clean `tsc`.
- Later phases invent Terminal/Book/Research/Counsel workflows only on top of
  a green gate.

## Consequences

**Positive**

- Redesign cannot silently break trading or ship with red CI.
- Agents and humans share one definition of “done.”

**Negative**

- Slower cosmetic iteration; validation cost before each commit.

**Neutral**

- Legacy page modules may remain behind OS routes until a later phase absorbs
  them, provided redirects and types stay green.

## Alternatives Considered

1. **Big-bang redesign behind a flag** — rejected; still risks long red branches.
2. **Allow `any` / disable lint to unblock UI** — rejected; reduces type safety.

## References

- ADR-0016 Trading OS Information Architecture
- ADR-0014 MT5 Is Adapter
- ADR-0015 AI Is Advisor
