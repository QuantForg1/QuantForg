# RC4 Brand Rebrand — Delivery Report

**Branch:** `cursor/rc4-brand-rebrand-bc83`  
**PR:** https://github.com/QuantForg1/QuantForg/pull/64  
**Authority:** Product-owner Design Freeze override (RC3 → RC4)

## Confirmation — UI layer only

| Layer | Changed? |
|---|---|
| Visual tokens / CSS | Yes |
| Brand assets / favicons / OG / PWA | Yes |
| Landing static HTML + React marketing page | Yes (presentation) |
| Auth shell / login chrome | Yes (presentation) |
| Shared UI primitives (button/input/card/dialog) | Yes (styles only) |
| Sidebar / loading brand mark | Yes (presentation) |
| Design Freeze / Design Bible docs | Yes (RC4 baseline) |
| Business logic / AI / trading / OMS / MT5 | **No** |
| APIs / auth flows / DB / routing / backend | **No** |
| State / permissions / feature flags / services | **No** |

Root `/` still rewrites to `go-live-landing.html` via `src/proxy.ts` (unchanged routing contract). That static file was visually rebranded to RC4.

## Branding summary

- **Official mark:** stylized Q (cyan) + F (white/silver) with candlesticks — `frontend/public/brand/quantforg-mark.png` (+ SVG, 256px web cut)
- **Primary:** turquoise / cyan `#00D4E0` (+ gradient `#5EF6FF → #00D4E0 → #0891A8`)
- **Secondary:** white / silver text
- **Neutrals:** charcoal `#111827` / `#151B23` / `#1A2330` / `#202938` (never pure black)
- **Atmosphere:** soft radial cyan lighting — **no grid**, no neon/hacker/crypto chrome
- **Typography:** IBM Plex Sans / Mono (unchanged family; hierarchy/spacing tightened)

## Design system summary (RC4 tokens)

Source of truth: `frontend/src/app/globals.css`

- Surfaces: `--bg`, `--bg-elevated`, `--surface`…`--surface-3`
- Accent: `--accent`, `--accent-gradient`, `--accent-soft`, `--accent-glow`, `.qf-btn-primary`
- Ambient: `--bg-ambient` (premium charcoal gradients)
- Focus: `--ring` cyan
- Motion: 160–220ms institutional easing (unchanged budgets)
- Components inherit tokens: Button, Input, Card, Dialog, EmptyState, Sidebar, AuthShell

## Replaced branding assets

| Asset | Path |
|---|---|
| Official mark (full) | `frontend/public/brand/quantforg-mark.png` |
| Official mark (web) | `frontend/public/brand/quantforg-mark-256.png` |
| Official mark (SVG) | `frontend/public/brand/quantforg-mark.svg` |
| Favicon ICO | `frontend/src/app/favicon.ico`, `frontend/public/favicon.ico` |
| Favicon 16/32 | `frontend/public/favicon-16x16.png`, `favicon-32x32.png` (+ brand/) |
| Apple Touch | `frontend/public/apple-touch-icon.png` (+ brand/, `apple-icon.tsx`) |
| PWA 192/512 | `frontend/public/icon-192.png`, `icon-512.png` (+ brand/) |
| App icon route | `frontend/src/app/icon.tsx` |
| Open Graph | `frontend/public/og-image.png` (+ brand/) |
| Web manifest | `frontend/public/manifest.webmanifest` |
| Static landing | `frontend/public/go-live-landing.html` |

Runtime brand component: `frontend/src/components/brand/brand-logo.tsx` (`BrandLogo`, `BrandMark`).

## Before / After screenshots

Artifacts: `/opt/cursor/artifacts/screenshots/rc4/`

| | Before (production RC3) | After (RC4) |
|---|---|---|
| Landing desktop | `before-landing-desktop.png` | `after-landing-desktop.png` |
| Login desktop | `before-login-desktop.png` | `after-login-desktop.png` |
| Landing mobile | — | `after-landing-mobile.png` |
| Login mobile | — | `after-login-mobile.png` |
| Landing tablet | — | `after-landing-tablet.png` |
| Register | — | `after-register-desktop.png` |
| Landing full | — | `after-landing-full.png` |

## Quality checks

- `tsc --noEmit`: clean
- ESLint on touched files: clean (no errors)
- Responsive: desktop / tablet / mobile screenshots captured
- A11y: focus rings retained (`--ring`), skip link retained, WCAG AA contrast target on charcoal+cyan
