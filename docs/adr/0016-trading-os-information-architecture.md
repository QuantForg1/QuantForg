# ADR-0016: Trading Operating System Information Architecture

## Status

Accepted

## Context

The frontend grew into dozens of peer routes (dashboard, workspace, execution,
portfolio, ops diagnostics, marketing onboarding). Traders faced duplicated
KPIs, stacked session widgets, and a product that felt like glued dashboards
rather than an operating system for an 8–12 hour session.

Backend, APIs, auth, MT5 gateway, Cloudflare, Railway, order execution,
websockets, TradingView, and Supabase must remain unchanged.

## Decision

**QuantForg is a trading OS with eight primary surfaces. Terminal is flagship.**

### Navigation maximum

| Surface | Job |
|---|---|
| Terminal | Trade — chart, ticket, blotter (`/terminal`) |
| Book | Portfolio, risk, P&L (`/book`) |
| Research | Build, test, validate (`/research`) |
| Counsel | Decision intelligence — advisory only (`/counsel`) |
| Journal | Session memory (`/journal`) |
| Broker | Session attach & connectivity (`/broker`) |
| Inbox | Alerts (`/notifications`) |
| Settings | Profile, org, prefs (`/settings`) |

Everything else is a redirect, drawer, modal, context panel, or command-palette
target. Ops/gateway diagnostics are not trader-rail items.

### Design rules

1. **Workflows over pages** — pixels must help trading decisions or be removed.
2. **Real data only** — no mock equity, fake PnL, fabricated AI, or demo charts
   in production. Unavailable data → empty state.
3. **Typography** — IBM Plex Sans + IBM Plex Mono; tabular figures for numbers.
4. **Visual language** — calm steel; no neon, no atmosphere gradients, no
   fintech clichés.
5. **AI** — invisible counsel (pre-trade, risk, journal), never a chatbot that
   invents prices or trades (extends ADR-0015).
6. **Motion** — 180–220ms, functional only.
7. **Post-login home** — `/terminal`. Onboarding tour does not auto-interrupt.

### Compatibility

Legacy paths redirect via `frontend/next.config.ts` (e.g. `/dashboard` →
`/book`, `/execution` → `/terminal`). Thin re-export pages preserve existing
page modules during migration without breaking deep links.

## Consequences

**Positive**

- One mental model; Terminal-centric muscle memory (⌘1–⌘4).
- Less duplication and diagnostic noise in trader chrome.
- Safe incremental rewrite without backend regressions.

**Negative**

- Temporary dual-path maintenance until legacy modules are fully absorbed.
- Redirect chains add a hop for old bookmarks.

**Neutral**

- Admin/ops tooling remains reachable via Settings or direct URL until
  admin-gated panels land.

## Alternatives Considered

1. **Keep 30+ nav items** — rejected; cognitive overload.
2. **Clone competitor terminal UX** — rejected; identity must be QuantForg’s.
3. **Big-bang delete of all legacy pages** — rejected; high production risk.

## References

- ADR-0014 MT5 Is Adapter
- ADR-0015 AI Is Advisor
- `frontend/src/components/layout/nav-config.ts`
- `frontend/next.config.ts` redirects
