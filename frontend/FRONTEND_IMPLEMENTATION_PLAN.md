# QuantForg Frontend Implementation Plan

**Product:** QuantForg Enterprise Frontend v1.0  
**Stack:** Next.js 15 · App Router · TypeScript · Tailwind CSS 4 · TanStack Query · RHF + Zod · Framer Motion · Recharts · next-themes  
**API:** Existing production backend only (`NEXT_PUBLIC_API_BASE_URL`)  
**Constraint:** No backend modifications  

---

## Design direction

- **Identity:** QuantForg as primary brand signal (landing + shell).
- **Palette:** Charcoal terminal surfaces with teal accent (not purple / cream-terracotta / newspaper).
- **Typography:** Sora (display) · Manrope (UI) · IBM Plex Mono (numerics).
- **Motion:** Landing hero entrance, feature stagger, command palette.
- **References:** Linear density, Stripe clarity, TradingView numerics, Bloomberg readability.

---

## Architecture

```
frontend/src
  app/
    page.tsx                 Landing
    (auth)/                  Login, register, forgot, verify
    (app)/                   Authenticated shell + product pages
  components/
    ui/                      Design system primitives
    layout/                  Sidebar, topbar, command palette, shell
    charts/                  Equity / performance charts
    trading/                 Order ticket
    auth/                    Auth chrome
    system/                  Offline banner
  lib/
    api/                     Typed fetch + refresh
    auth/                    Token session (localStorage)
    env.ts                   Public env only
  providers/                 Theme, Query, Auth
```

---

## Phases

| Phase | Scope | Status |
|-------|--------|--------|
| 0 | Scaffold Next.js 15 + deps | Done |
| 1 | Design tokens + UI kit | Done |
| 2 | Auth + API client + session refresh | Done |
| 3 | App shell, nav, command palette | Done |
| 4 | Dashboard + portfolio/trading surfaces | Done |
| 5 | Research (strategy, backtest, paper, risk, AI) | Done |
| 6 | Account (profile, settings, orgs, notifications, support) | Done |
| 7 | Empty/loading/error/offline + a11y basics | Done |
| 8 | Docs + build verification | Done |

---

## API mapping

| UI | Backend |
|----|---------|
| Login / Register / Me / Refresh | `/auth/*` |
| Portfolio / Positions / Orders / History | `/portfolio`, `/positions`, `/orders`, `/history` |
| MT5 connect/status | `/mt5/*` |
| Brokers | `/brokers`, `/broker-accounts`, `/broker-connections` |
| Risk / Strategy / Backtest / Paper / Execution | matching `/risk`, `/strategy`, `/backtests`, `/paper`, `/execution` |
| Profile / Settings / Notifications / Orgs | `/profile`, `/settings`, `/notifications`, `/organizations` |

Live `order_send` stays gated by backend `EXECUTION_ENABLED=false`.

---

## Environment

```bash
NEXT_PUBLIC_API_BASE_URL=https://quantforg-production.up.railway.app/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_MOCK_AI=true
```

Never put secrets in `NEXT_PUBLIC_*`.

---

## Success criteria

- All listed routes render responsively
- Auth required for `(app)/*`
- No fabricated backend endpoints
- TypeScript + ESLint clean on build
- Enterprise visual quality (shell + landing + dashboard + order ticket + AI)
