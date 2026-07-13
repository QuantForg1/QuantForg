# Beta Readiness Report

**Product:** QuantForg  
**Scope:** Closed beta / enterprise operational readiness (observability, reliability, ops controls)  
**Date:** 2026-07-13  
**Constraint:** No UI redesign, no product feature expansion, no backend architecture/schema/auth/API contract changes. MT5 + RealtimeEngine preserved.

## Summary

QuantForg frontend now ships production-oriented observability and beta controls without changing trading business logic or API contracts:

| Capability | Status |
|---|---|
| Error monitoring (runtime, React, API, execution, MT5, rejections, routes) | Done |
| Client audit logging (auth, broker, orders, settings, orgs) | Done |
| Operations dashboard enrichment | Done |
| In-app feedback widget | Done |
| Feature flags (AI / MT5 / Paper / Workspace / Beta) | Done |
| Closed beta / maintenance / read-only modes | Done |
| Health diagnostics surface on Ops | Done (uses existing `/health`, `/ops/*`) |
| Operator documentation | Done |

## Architecture notes

- **Client-side first:** Errors, audit events, and feedback are captured in-browser (ring buffers + optional webhooks via env). This avoids schema/API changes.
- **Server ops APIs unchanged:** Ops page continues to call existing `GET /health`, `GET /ops/dashboard`, `GET /ops/metrics`, `GET /ops/alerts`, `GET /ops/audit`, `GET /mt5/status`, `GET /version`.
- **Secrets never logged:** `sanitizePayload` redacts password/token/secret/authorization/cookie/api_key/refresh fields.
- **Feature toggles:** `NEXT_PUBLIC_FF_*` env defaults + `localStorage` overrides (`qf.ff.overrides.v1`) — no code deploy required for overrides.
- **Beta invite:** Client-side unlock against `NEXT_PUBLIC_BETA_INVITE_CODE` (operator control, not cryptographic access control). Combine with auth + server RBAC for real security.

## Error context fields

Every monitored error includes: `request_id`, `user_id` (when authenticated), `route`, `browser`, `build_version`, plus kind/message/stack/status/path when available.

## Remaining operator actions

1. Set production env vars on Vercel (flags, beta mode, webhooks, build version).
2. Configure `NEXT_PUBLIC_ERROR_WEBHOOK_URL` / `AUDIT` / `FEEDBACK` to your SIEM or Slack/Make endpoint.
3. Confirm Railway `/health` dependencies include DB/Redis/MT5 as expected for your tier.
4. Invite closed-beta users; distribute invite code out-of-band.
5. Keep `NEXT_PUBLIC_MOCK_AI=false` in production.
6. Run a smoke pass after deploy: login → ops → MT5 status → place/cancel paper order if enabled.

## Validation

See commit notes / CI output for `npm run typecheck`, `lint`, `build`, and backend tests.
