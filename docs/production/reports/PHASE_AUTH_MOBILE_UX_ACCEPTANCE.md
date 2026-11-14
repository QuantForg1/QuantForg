# PHASE — Authentication, Google OAuth & Mobile UX Acceptance

**Date:** 2026-11-14  
**Branch:** `fix/auth-oauth-mobile-ux`  
**Production:** https://www.quantforg.com  
**API:** https://quantforg-production.up.railway.app  

| Gate | Status |
|------|--------|
| Registration (Production) | **BLOCKED** — Supabase Auth email rate limit |
| Google OAuth start URL | **PASS** — Production `redirect_to` |
| Google OAuth end-to-end return | **BLOCKED** — Owner must set Supabase Site URL + Redirect allowlist |
| Auth error messages (code) | **PASS** (code + tests) |
| Mobile shell / terminal UX | **PASS** (code) — Production deploy pending |
| CI / merge / deploy SHA | **PENDING** until PR merge |

---

## 1. Registration root cause and fix

### Root cause (verified)

Live probe against Production API:

```http
POST /api/v1/auth/register
→ Supabase Auth HTTP/2 429
→ provider_message: "email rate limit exceeded"
→ API: auth_rate_limited / HTTP 429
```

Railway log evidence (2026-11-14):

- `HTTP Request: POST …/auth/v1/signup "HTTP/2 429 Too Many Requests"`
- `supabase_auth_rate_limited … provider_message='email rate limit exceeded'`

Users who only see a toast may still describe this as “Authentication failed” when an older UI/path maps generic 401s; Production API now returns a specific rate-limit message when the code path is `auth_rate_limited`.

This is **not** a frontend form bug and **not** a Postgres profile-trigger failure. Sign-up is rejected by Supabase’s built-in email send quota before a durable session is issued.

### Code fixes shipped

| Change | Purpose |
|--------|---------|
| Broader `_map_auth_error` + GoTrue field extraction | Map 429 / duplicate / weak password / signup disabled / OAuth disabled |
| Expanded `error_handler` public messages | Stop collapsing actionable codes into generic “Authentication failed” |
| `email_redirect_to` on `sign_up` from `AUTH_REDIRECT_URL` | Confirmation links target configured Production callback |
| Register page handles 409 / 429 explicitly | Duplicate → login; rate limit → clear wait / Google guidance |

### Owner action required (cannot be fixed in-repo alone)

1. Supabase → Authentication → **SMTP**: configure custom SMTP (e.g. Resend) **or** upgrade plan so Auth confirmation email is not hard-capped.  
2. Do **not** disable email confirmation in Production to bypass the limit.  
3. After SMTP/quota is fixed, re-probe `POST /api/v1/auth/register` until **201** with session or verify-email message.

---

## 2. Google OAuth root cause and fix

### Root cause

OAuth **start** from Production API is correct:

```text
GET /api/v1/auth/oauth/google?redirect_to=https://www.quantforg.com/auth/callback
→ 200
→ authorize URL contains redirect_to=https://www.quantforg.com/auth/callback
```

Railway `AUTH_REDIRECT_URL` is already `https://www.quantforg.com/auth/callback`.

Landing on `http://localhost:3000/?code=…` means Supabase fell back to **Site URL** (still localhost and/or bare `/`) because the Production callback was not accepted from the Redirect allowlist, or Site URL remains localhost.

### Code fixes shipped

| Change | Purpose |
|--------|---------|
| `frontend/src/middleware.ts` | If IdP returns `/?code=` or `/?error=` on Production host, forward to `/auth/callback` |
| Google button localhost guard | Refuse to follow authorize URLs that would return localhost while on `*.quantforg.com` |
| `oauth-origin-guard` helper + test | Regression coverage for the Production localhost heuristic |
| Docs (`GOOGLE_OAUTH_SETUP.md`) | Explicit Site URL / SMTP / never-localhost guidance |

### Owner action required

Supabase → Authentication → URL configuration:

| Setting | Required value |
|---------|----------------|
| **Site URL** | `https://www.quantforg.com` (**not** `http://localhost:3000`) |
| Redirect URLs | `https://www.quantforg.com/auth/callback` |
| | `https://quantforg.com/auth/callback` |
| | `http://localhost:3000/auth/callback` (local only) |

Google Cloud → Authorized redirect URI must remain the **Supabase** callback:  
`https://otqyhlmwaifokrczryrc.supabase.co/auth/v1/callback`

---

## 3. External configuration still required

| Item | Owner | Status |
|------|-------|--------|
| Supabase Site URL = `https://www.quantforg.com` | Supabase Owner | **BLOCKED** / unverified in Dashboard from this agent |
| Supabase Redirect URLs include Production `/auth/callback` | Supabase Owner | **BLOCKED** / unverified |
| Supabase custom SMTP or plan upgrade for Auth email | Supabase Owner | **BLOCKED** |
| Railway `AUTH_REDIRECT_URL` | Railway | **PASS** (observed) |
| Vercel `NEXT_PUBLIC_APP_URL` | Vercel | Assumed Production; confirm after deploy |

---

## 4. Production authentication test evidence

| # | Case | Result |
|---|------|--------|
| 1 | New user registration | **BLOCKED** — `auth_rate_limited` / 429 |
| 2 | Existing email registration | Not re-tested while rate-limited (mapping covered in unit tests) |
| 3 | Email/password login | Not executed with live credentials in this phase |
| 4 | Invalid password | Mapping covered (`invalid_credentials`) |
| 5 | Email verification | Blocked upstream (confirmation email not sent under rate limit) |
| 6 | Google OAuth initiation | **PASS** — authorize URL with Production `redirect_to` |
| 7 | Google OAuth callback | **BLOCKED** pending Site URL / allowlist Owner fix |
| 8 | PKCE exchange | Code path unchanged; blocked without successful callback landing |
| 9 | Session persistence | Deferred until auth succeeds |
| 10 | Logout | Unchanged API; deferred interactive |
| 11 | Password reset | Uses same redirect sanitizer; deferred interactive |
| 12 | Protected routes | App shell still redirects unauthenticated users to `/login` |
| 13 | Mobile browser auth | Deferred until deploy + Owner config |
| 14 | Production redirect behavior | Start **PASS**; return **BLOCKED** on Site URL |

Safe probe email pattern used: `authprobe+{guid}@example.com` (no secrets logged).

---

## 5. OAuth redirect evidence

- API authorize URL (truncated):  
  `…/auth/v1/authorize?redirect_to=https%3A%2F%2Fwww.quantforg.com%2Fauth%2Fcallback&…&provider=google`
- Defense-in-depth: Next middleware remaps `/?code=` → `/auth/callback` on the **deployed** host (does not fix redirects that already left the browser for localhost).

---

## 6. Responsive viewport test matrix

| Viewport | Shell / nav | Terminal | Notes |
|----------|-------------|----------|-------|
| 360 | Code PASS | Code PASS | Tokens + tab bar + FAB offset |
| 375 | Code PASS | Code PASS | |
| 390 | Code PASS | Code PASS | |
| 414 | Code PASS | Code PASS | |
| 430 | Code PASS | Code PASS | |
| 768 | Code PASS | Code PASS | `md` metrics row |
| 1024 | Code PASS | Code PASS | Sidebar / desktop terminal |
| 1440 | Code PASS | Code PASS | |

Interactive browser matrix on Production after deploy: **PENDING**.

---

## 7. Mobile navigation improvements

- Shared `--shell-mobile-*` CSS contract for tab height, content pad, FAB clearance  
- Bottom tab bar: active accent chip, consistent spacing, safe-area  
- Drawer: compact brand, safe-area, footer hint for full desk list  
- Topbar: less clutter on compact / phone (logout from `sm+`, tighter heights)  
- Page header: mobile title scale + full-width actions  

---

## 8. `/terminal` mobile improvements

- Session bar: two-row mobile (status/account + symbol/metrics); single-row desktop preserved  
- Chart-first: blotter collapsed preference on mobile first paint; counsel collapsed  
- BUY/SELL bar clears tab bar + open blotter via CSS vars  
- Blotter tabs larger / scrollable on phone  
- Dense controls marked `data-compact` so global 44px floor does not explode chrome  

Trading safety / OMS / risk checks unchanged.

---

## 9. Routes audited (layout / responsive)

`/`, `/login`, `/register`, `/dashboard`, `/signals`, `/positions`, `/history`, `/broker`, `/terminal`, `/research`, `/strategy` (strategies), `/risk-center`, `/settings`, `/support`, plus Admin shell (separate; no trader tab bar). Shared `AppShell` + desk shells; page-level settings/dashboard spacing adjusted.

---

## 10. Bugs fixed (code)

1. Generic auth toast for mapped codes (expanded public messages)  
2. Weak GoTrue error extraction for rate limits / duplicates  
3. Signup confirmation redirect tied to `AUTH_REDIRECT_URL`  
4. OAuth bare-`/` code landing → `/auth/callback` middleware  
5. Production Google button can refuse localhost authorize URLs  
6. Mobile terminal chrome crowding (session, FAB, blotter, tab clearance)  
7. Mobile nav density / active state clarity  

---

## 11. CI and test results

| Check | Result |
|-------|--------|
| `tests/unit/test_auth_error_mapping.py` | Added — run in CI / `.venv` |
| `frontend/src/lib/auth/oauth-origin-guard.test.ts` | Node assert pattern |
| Frontend `tsc --noEmit` | Reported clean in implementation pass |
| Full CI | **PENDING** on PR |

---

## 12. PR links and merge commits

| Item | Value |
|------|-------|
| PR | *filled after `gh pr create`* |
| Merge commit | *pending* |

---

## 13. Vercel / Railway deployment SHA

| Surface | SHA |
|---------|-----|
| Frontend (Vercel) | *pending deploy* |
| Backend (Railway) | Pre-change observed deployment `ee90fe44-4ada-40e7-9296-5e420cb1d604` — new SHA after merge |

---

## 14. Remaining blockers

1. **BLOCKED:** Supabase Auth email rate limit / missing custom SMTP — blocks real registration.  
2. **BLOCKED:** Supabase Site URL / Redirect allowlist — blocks reliable Google return to Production (prevents localhost fallback).  
3. **PENDING:** Merge + Vercel/Railway deploy of this branch; then re-run interactive auth + mobile browser matrix.

**Overall:** Not 100% Production-complete. Code and evidence for root causes are in place; Owner Dashboard actions above are required for PASS on live signup and Google return.
