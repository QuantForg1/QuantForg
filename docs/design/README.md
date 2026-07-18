# QuantForg Design Bible

**Status:** Binding  
**Phase:** P4.5  
**Governing ADR:** [ADR-0022](../adr/0022-design-bible-and-product-governance.md)

This is the permanent product and design constitution for QuantForg.

QuantForg is an **institutional trading operating system**. Traders live inside it for 8–12 hours a day. The product must disappear so trading decisions remain clear.

Every pixel, component, and feature must answer:

> Does this help someone make a better trading decision?

If **no** — delete it or do not ship it.

---

## Binding documents

| # | Document | Purpose |
|---|---|---|
| 1 | **This Design Bible** | Master constitution |
| 2 | [Product Governance](product-governance.md) | Who decides; what is sacred |
| 3 | [Feature Lifecycle](feature-lifecycle.md) | Idea → ship → retire |
| 4 | [UX Principles](ux-principles.md) | Interaction & workflow law |
| 5 | [Design Tokens](design-tokens.md) | Color, space, motion tokens |
| 6 | [Typography](typography.md) | IBM Plex hierarchy |
| 7 | [Accessibility](accessibility.md) | A11y standards |
| 8 | [Performance Budgets](performance-budgets.md) | Speed & weight limits |
| 9 | [Component Acceptance](component-acceptance-checklist.md) | New UI gate |
| 10 | [Feature Acceptance](feature-acceptance-checklist.md) | New feature gate |

**Every future PR that touches product UI or workflow must comply.**

---

## Product identity

QuantForg must **not** resemble:

- MetaTrader 5
- TradingView
- Binance / Bybit
- cTrader
- Thinkorswim
- Interactive Brokers
- Bloomberg Terminal (clone)

It must have its **own** calm, institutional identity:

- Apple precision
- Stripe consistency
- Linear simplicity
- Steel palette — no neon, no atmosphere gradients, no fintech clichés

---

## Information architecture (maximum)

| Surface | Job | Flagship? |
|---|---|---|
| **Terminal** | Trade | Yes |
| **Book** | Understand portfolio | |
| **Research** | Idea → promote | |
| **Counsel** | Decide (never execute) | |
| **Journal** | Session memory | |
| **Broker** | Attach session | |
| **Inbox** | Alerts | |
| **Settings** | Prefs / org | |

Everything else is drawer, modal, context panel, command palette, or redirect.

See ADR-0016–0021.

---

## Non-negotiable preserves

Never regress without an explicit ADR and release plan:

1. Production functionality  
2. MT5 order execution path  
3. Backend / API / websocket / Supabase contracts  
4. Authentication  
5. Terminal as sole execution surface  
6. Real data only (or elegant empty states)  
7. Continuously releasable CI (`tsc`, ESLint, build, tests)

---

## Visual & motion law (summary)

- **No** neon, glow stacks, purple fintech gradients, atmosphere mesh backgrounds  
- **Yes** steel tokens in `frontend/src/app/globals.css`  
- Motion: **180–220ms**, functional only (`--duration-os`, `--ease-os`)  
- Numbers: **tabular** everywhere (`font-variant-numeric` / `.tabular` / mono)  
- Fonts: **IBM Plex Sans** + **IBM Plex Mono** only for product UI  

Full detail: [design-tokens.md](design-tokens.md), [typography.md](typography.md).

---

## Data integrity law

- 100% production or live session data for trading surfaces  
- No mocks, fabricated PnL, fake charts, fake AI replies, demo balances in production  
- Unavailable data → Empty State (never invent)  
- AI advises; never invents prices/trades; never places orders (ADR-0015)

---

## Quality bar

Before keeping any component, ask:

- Would Apple ship this?
- Would Stripe ship this?
- Would Linear ship this?
- Would Figma ship this?
- Would it survive an institutional desk review?

If not — redesign.

---

## Enforcement

| Layer | Mechanism |
|---|---|
| Docs | This folder + ADR-0022 |
| Agents | `.cursor/rules/quantforg-design-bible.mdc` |
| Humans | PR template + Code Review + Definition of Done |
| CI | Governance docs presence job |

Violations block merge unless an ADR supersedes the rule.
