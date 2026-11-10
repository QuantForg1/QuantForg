# Phase 8.6 — Customer Multi-Account UX audit + contract

**Status:** Audit + API contract prepared. **No Design Freeze override.**  
Do not ship fake Connected / Verified / Worker Online states.

## Existing surfaces (preserve)

| Surface | Role |
|---|---|
| `frontend/.../broker` + `broker-config-workspace.tsx` | Customer MT5 connect / Demo vs Live server distinction |
| `GET /api/v1/multi-account/dispatch/status` | Customer-scoped dispatch jobs + blocked reasons |
| Admin ` /admin/multi-account` (Phase 7) | Owner ops only — not a customer desk |

## Required customer truths (no fabrication)

- Broker accounts: real connection payload or elegant empty state
- Demo / Live: inferred from broker server metadata only
- Eligibility: `eligibility.blocked_reasons` from API (e.g. `multi_account_dispatch_disabled`)
- Dispatch status: own jobs only from durable queue
- Worker availability: customer payload sets `reported=false` until ownership-bound assignment exists
- Connection verification: `verified=false` until broker evidence is recorded
- Never show credentials, worker tokens, sealed envelopes, or other users' data

## Blocked-state copy (recommended)

When `eligibility.blocked` is true:

> Multi-account dispatch is not enabled for your account yet. Live order fan-out remains off.

When connection verification is false:

> Broker ownership is not verified. Connect and complete verification before dispatch eligibility can pass.

## Out of scope until Owner proof

- New visual patterns / redesign of Broker desk (RC4 freeze)
- Enabling Connected badges from registration alone
- Surfacing control-plane worker heartbeats to customers
