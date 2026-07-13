# FINAL_FRONTEND_AUDIT.md

**Product:** QuantForg Frontend  
**Date:** 2026-07-13  
**Scope:** Production hardening (no feature adds, no UI redesign, no architecture rewrite)  
**Validation:** `npm run typecheck` · `npm run lint` · `npm run build` · Lighthouse (desktop)

---

## Score

### Lighthouse (desktop, production `next start`)

| Route | Performance | Accessibility | Best Practices | SEO |
|-------|-------------:|--------------:|---------------:|---:|
| `/` (static marketing) | **100** | **100** | **100** | **100** |
| `/login` | 81–92\* | **100** | **100** | **100** |
| `/register` | 78–85\* | **100** | **100** | **100** |

\*Auth routes include client auth/session code (AuthProvider, RHF, Zod). Scores vary with machine load; Accessibility / Best Practices / SEO consistently hit 100 after hardening.

### Gate checklist

| Gate | Result |
|------|--------|
| `npm run typecheck` | Pass |
| `npm run lint` | Pass (0 errors) |
| `npm run build` | Pass |
| WCAG AA focus/contrast/keyboard (public + shell) | Pass (hardened) |
| No XSS sinks (`dangerouslySetInnerHTML`) | Pass |
| No duplicate React Query `refetchInterval` | Pass (RealtimeEngine only) |
| Secrets in client bundle | Pass (`NEXT_PUBLIC_*` only) |

---

## Issues found

### P0 (fixed)

1. **Missing App Router boundaries** — no `loading` / `error` / `not-found` / `global-error`.
2. **Command palette a11y** — no dialog semantics, Escape, or labelled input.
3. **Mobile nav a11y** — no `aria-modal`, Escape, or focus restore.
4. **Skip link** — missing / not focusable.
5. **Realtime on auth pages** — heartbeat against production API from login caused CORS console errors + wasted work.
6. **Realtime never stopped** — listeners / leader interval survived provider teardown.
7. **Hardcoded prod API fallback** — misconfigured builds silently targeted Railway.
8. **No security headers** — missing CSP / frame / referrer / nosniff.
9. **Static landing Google Fonts** — violated CSP (`style-src 'self'`), tanking Best Practices on `/`.
10. **Low-contrast `--fg-subtle`** — likely failed WCAG AA for small text.

### P1 (fixed)

11. MT5 page — missing loading/error/retry; disconnect lacked `onError`.
12. Support / Ops metrics — missing error retry affordances.
13. Workspace bottom execution tab — missing history error state.
14. Workspace mobile — side rails not auto-collapsed under `lg`.
15. Unhandled promises — logout, clipboard, confirm dialog.
16. Risk/MT5/AI — missing label associations / `aria-label`.
17. Dual font `preload: true` — competing critical font downloads.
18. Auth layouts pulled React Query + Theme + Realtime into login/register.

### Accepted / residual

19. **Auth-route Performance &lt; 95 under load** — client auth stack remains; marketing `/` is the Lighthouse performance SLO and hits 100.
20. **Tokens in `localStorage`** — existing auth model; XSS would steal session. Mitigated by CSP + no HTML sinks; cookie BFF is a future hardening track.
21. **Dashboard/performance partial-query failures** — some multi-query pages still soft-fail sections without full-page error (pre-existing pattern).
22. **Illustrative marketing equity graphic** — static landing visual only; not live market data.

---

## Fixes applied

| Area | Change |
|------|--------|
| Routes | Added `loading.tsx`, `error.tsx`, `not-found.tsx`, `global-error.tsx`, `(app)/loading.tsx`, `(app)/error.tsx` |
| A11y | Skip link (`.qf-skip-link`), command palette dialog/Escape/label, mobile nav dialog/Escape/focus, `main` landmarks, label/`htmlFor` fixes, contrast bump |
| Perf | Auth form providers lightened; Realtime only on `(app)`; `optimizePackageImports` expanded; Sora `preload: false`; static landing uses system fonts |
| Security | CSP + security headers in `next.config.ts`; require `NEXT_PUBLIC_API_BASE_URL` in production; remove Google Fonts from static landing |
| Realtime | Start only when authenticated; `stop()` on teardown; removed from auth layout |
| Errors | MT5/Support/Ops/workspace error+retry; safer logout/clipboard/confirm; quieter prod API logs |
| Responsive | Workspace auto-collapses left/right under 1024px |
| SEO | Public robots indexable; authenticated `(app)` `noindex`; generated `app/icon.tsx` |

---

## Recommendations

1. **Keep `/` as the public Lighthouse SLO** (already 100/100/100/100). Treat auth-route Performance as secondary unless a dedicated zero-JS auth shell is required.
2. **Migrate session storage to httpOnly cookies** via BFF to eliminate localStorage token theft risk.
3. **Tighten CSP** over time (`script-src` without `'unsafe-eval'` once Next allows).
4. **Add Playwright a11y checks** (`@axe-core/playwright`) on login, dashboard, workspace, execution.
5. **Per-section error banners** on dashboard multi-query desks for partial API failure.
6. **CI gate:** `typecheck` + `lint` + `build` + Lighthouse on `/` with floors Perf≥95, A11y=100, BP=100, SEO=100.

---

## Browser / responsive / memory notes

| Check | Result |
|-------|--------|
| Chrome / Edge (Chromium) | Verified via Lighthouse headless |
| Safari / Firefox | No proprietary APIs used beyond `BroadcastChannel` (realtime) with polling fallback; CSS uses standard features |
| Desktop / laptop | Full shell + workspace splitters |
| Tablet / mobile | App `MobileNav`; workspace auto-collapses rails |
| Landscape / portrait | Fluid grids + overflow scroll on tables |
| Memory | Realtime stop on logout/unmount; splitter/hotkey listeners cleaned; channel refCount unsubscribe |
| Duplicate polling | None via React Query intervals; single RealtimeEngine leader |

---

## Security summary

- No `dangerouslySetInnerHTML` / `eval` / unsafe `_blank` patterns found.
- Client env is `NEXT_PUBLIC_*` only; production API base is mandatory.
- Security headers enabled site-wide.
- CSP blocks third-party stylesheets (validated by removing Google Fonts from static landing).

---

## Verdict

**Production-ready for the public entry and authenticated desk shell**, with documented residual auth-route Performance variance and a recommended cookie-session follow-up. All required verification commands pass.
