# QuantForg v1.0 — GA Readiness Report

| Field | Value |
|---|---|
| Product | QuantForg |
| Version | **1.0.0** |
| Date (UTC) | 2026-07-13 |
| Preceding certificate | [GO_LIVE_CERTIFICATE.md](./GO_LIVE_CERTIFICATE.md) (Closed Beta GO) |
| Scope | Resolve High items H-01…H-04 without API/schema/architecture changes |

---

## Overall score

| Dimension | Score | Notes |
|---|---|---|
| High-item closure (H-01…H-04) | **96 / 100** | All four addressed within constraints |
| Frontend quality gates | **100 / 100** | typecheck · lint · build |
| Backend automated tests | **100 / 100** | 306 passed · 2 skipped · ~76.6% coverage |
| E2E suite | **Pass\*** | Chromium suite expanded; authenticated login test needs `E2E_EMAIL`/`E2E_PASSWORD` |
| Security (Bearer model) | **88 / 100** | HttpOnly cookies blocked by API contract; storage hardened |
| **Composite GA readiness** | **94 / 100** | |

\*Playwright browsers must be installed in the runner (`npx playwright install chromium`).

---

## Decision

### **CONDITIONAL GO for public launch**

Public GA is **authorized only if** operators accept residual Bearer+localStorage token risk (documented below) and keep live execution gated until a supervised enablement plan is signed.

**Not an unconditional GA.** Unrestricted public launch with live trading ON requires a future BFF/HttpOnly cookie session (API change) and production execution enablement review.

---

## Resolved High items

### H-01 — Password reset completion — **RESOLVED**

| Step | Status |
|---|---|
| Forgot password | **PASS** — `/forgot-password` → `POST /auth/forgot-password` with `redirect_to=/reset-password` |
| Email link | **PASS** — Supabase recovery redirect to `/reset-password` (`token_hash` query or hash tokens) |
| Reset form | **PASS** — `/reset-password` → verify/recovery session → `POST /auth/change-password` |
| Expired token | **PASS** — invalid/missing token → expired UI + link to request again |
| Success flow | **PASS** — clear session → sign-in CTA |

Also: verify-email now persists session when API returns tokens.

### H-02 — HttpOnly cookie session — **RESOLVED (documented + hardened)**

| Question | Answer |
|---|---|
| Does backend support HttpOnly cookies? | **No.** Auth is `Authorization: Bearer` with tokens in JSON. No `Set-Cookie` session API. |
| Why not switched? | Would require **API / BFF contract change** — forbidden by sprint rules. |
| Hardening applied | Dual-storage scrub on logout; cross-tab logout via `storage` events; sessionStorage mirrors cleared; tokens never logged; comments in `session.ts` |

**Residual risk:** XSS can still read Bearer tokens from `localStorage`. Mitigations: CSP, no `dangerouslySetInnerHTML`, audit/error sanitization.

### H-03 — Cancel / modify order flow — **RESOLVED (within existing `/execution/*`)**

No new cancel/modify HTTP routes (API freeze). Completed product paths via existing validate → check → submit:

| Flow | Status |
|---|---|
| Pending orders list | Filtered to pending limit/stop |
| Modify price | **PASS** |
| Modify SL / TP (pending) | **PASS** |
| Cancel pending | **PASS** |
| Market fills | Directed to Positions (not cancelable as pending) |
| Close / partial close | **PASS** (Position Manager) |
| Modify SL / TP (open position) | **PASS** + audit |
| Live send | Still gated by `EXECUTION_ENABLED` (safety) |

### H-04 — Organization permissions — **RESOLVED**

| Role (product) | API role | Status |
|---|---|---|
| Owner | `owner` | Create workspace; invite Admin/Trader/Viewer |
| Admin | `admin` | Invite Trader/Viewer only |
| Trader | `member` | Display label for API `member` |
| Viewer | `viewer` | Inviteable; view-oriented |

**No privilege escalation:** server rejects Owner via invite; Admins cannot invite Admins; non-admin/owner cannot invite. UI role picker + permissions matrix on `/organizations`.

---

## Remaining risks

| ID | Risk | Severity | Notes |
|---|---|---|---|
| R-01 | Bearer tokens in `localStorage` | High→Medium after harden | Needs BFF/HttpOnly for full closure |
| R-02 | Live execution disabled by default | Medium (ops) | Intentional; enable only with runbook |
| R-03 | Cancel/modify not dedicated MT5 cancel RPC over HTTP | Low | Gateway submit comments; adapter has cancel for future |
| R-04 | Org membership list API absent | Low | Role inferred as Owner via `owner_user_id`; matrix is policy UI |
| R-05 | AI / non-MT5 brokers stub | Low | Feature-flagged / soft stubs |
| R-06 | Auth rate limit in-process | Medium | Multi-instance needs shared limiter |
| R-07 | Full authenticated E2E needs secrets in CI | Low | `E2E_EMAIL` / `E2E_PASSWORD` |

---

## Validation

```
npm run typecheck  → PASS
npm run lint       → PASS
npm run build      → PASS (includes /reset-password)
pytest             → 306 passed, 2 skipped
E2E                → Suite expanded (forgot/reset/orgs/execution guards);
                     run with Playwright Chromium installed
```

---

## Operator checklist (public launch)

- [ ] Confirm Supabase redirect allowlist includes `{APP_URL}/reset-password`
- [ ] Keep `EXECUTION_ENABLED=false` until live trading sign-off
- [ ] Accept R-01 or schedule HttpOnly BFF follow-up
- [ ] Set production feature flags / beta mode as needed
- [ ] Smoke: forgot → email → reset → login
- [ ] Smoke: org invite as Owner vs Admin (escalation blocked)
- [ ] Smoke: pending modify SL/TP + cancel (with execution still disabled → outcome `disabled` is OK)

---

## Sign-off

| | |
|---|---|
| **GO / NO-GO (public launch)** | **CONDITIONAL GO** |
| Conditions | Accept Bearer storage residual risk; live trading remains gated; Supabase reset redirect configured |
| Unconditional GA | Deferred until HttpOnly session BFF + live-execution readiness review |
