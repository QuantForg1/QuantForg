# QuantForg Frontend Progress

**Updated:** 2026-07-13  

## Completed

- [x] Next.js 15 App Router project under `frontend/`
- [x] Design system tokens (color, type, elevation, glass surfaces)
- [x] UI kit: Button, Input, Label, Card, Badge, Skeleton, Separator, EmptyState, ErrorBoundary
- [x] Providers: Theme, TanStack Query, Auth, Toasts
- [x] API client with Bearer auth + refresh-token retry
- [x] Landing page (brand-first hero + feature strip + motion)
- [x] Auth: Login, Register, Forgot Password, Verify Email
- [x] App shell: sidebar, topbar, ⌘K command palette, offline banner
- [x] Dashboard with live portfolio/MT5 queries + equity chart
- [x] Pages: Portfolio, Performance, Wallet, Brokers, MT5, Risk, Strategy, Backtesting, Paper, Execution, Orders, Positions, History, Analytics, AI, Notifications, Settings, Organizations, Profile, Support
- [x] Order ticket → MT5 validate + execution safety check
- [x] MT5 connect/disconnect forms
- [x] AI workspace UI (mock replies behind `NEXT_PUBLIC_MOCK_AI`)

## In progress / follow-ups

- [ ] Wire richer typed OpenAPI client generation from `openapi/openapi.json`
- [ ] Expand Performance/Analytics charts with historical series when endpoints expose them
- [ ] Mobile nav drawer (desktop sidebar complete; compact breakpoint uses top search)
- [ ] E2E Playwright suite against staging API
- [ ] Deploy frontend to Vercel with production CORS allowlist on Railway

## Verification checklist

| Check | Result |
|-------|--------|
| Backend unmodified | Yes |
| Secrets not in client | `NEXT_PUBLIC_*` only |
| EXECUTION_ENABLED respected | UI only validates/checks |
| `npm run typecheck` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| Docs | Plan + inventory + this file |
