# PHASE — Production Signup HTTP 422 / Confirmation Email

**Date:** 2026-11-14 → 2026-11-15  
**Code PR:** https://github.com/QuantForg1/QuantForg/pull/278 (merged)  
**Docs closeout:** https://github.com/QuantForg1/QuantForg/pull/279 (merged)

| Gate | Status |
|------|--------|
| Exact Auth error metadata captured | **PASS** |
| Root cause classified | **PASS** (see §2) |
| Signup creates user | **PASS** |
| Confirmation email → Resend | **PASS** (SMTP accepted; see delivery notes) |
| Confirm verify + hash auto-login | **PASS** (browser) |
| Session persist / logout / login | **PASS** (browser) |
| Specific API error mapping | **PASS** on Railway `c904fd0b` |
| `/qf-api` same-origin proxy on www | **PASS** |
| Google OAuth authorize redirect | **PASS** (no localhost) |
| `ite_ops_alerts` null `id` | **SEPARATE** — unchanged |

---

## Independent deployment SHAs

| Surface | SHA / tip | Evidence |
|---------|-----------|----------|
| **Railway Production** | `c904fd0b17722a20fdd129ba9cd610a33e1cd317` | `GET https://quantforg-production.up.railway.app/health` |
| **Vercel www** | Deployment `dpl_E6qqt8wQDfuXeAyL9VpSoCqVb7Mg` (`quant-forg-kspns9m29…`) containing #278 frontend (build meta `76b4107d…` / merged tip `c904fd0b`) | `vercel alias set` → www; `GET https://www.quantforg.com/qf-api/health` → Railway health JSON |

**Vercel note:** `vercel promote` / new Production builds remained rate-limited (`api-deployments-free-per-day`). Production was completed by **aliasing the already-built Ready preview** that contained the #278 frontend onto `www.quantforg.com` and `quantforg.com` — no new build, no env var changes, no protection bypass.

---

## Browser E2E — email confirmation auto-login (2026-11-15)

| Step | Result |
|------|--------|
| Register on `www.quantforg.com/register` | **PASS** → `/verify-email` |
| Confirmation email created | Resend id `01a1dc9c-a062-…` from `no-reply@auth.quantforg.com` (`last_event: bounced` for this plus-address probe; link body still valid) |
| Open Supabase verify link | **PASS** → `https://www.quantforg.com/auth/callback#access_token=…&type=signup` |
| Hash hydrate + session | **PASS** — callback showed “Completing sign-in…” then routed to `/get-started` (authenticated shell) |
| Refresh / navigate | **PASS** — session tokens persist; password login to `/dashboard` as `signup.frontend+promote8aea@gmail.com` |
| Sign out | **PASS** — Settings → Danger Zone → Sign out → `/login`, tokens cleared |
| Sign back in | **PASS** → `/dashboard` with same account |
| Google OAuth start | **PASS** — `GET /qf-api/api/v1/auth/oauth/google?redirect_to=…/auth/callback` returns authorize URL with `redirect_to=https://www.quantforg.com/auth/callback` (no localhost); `/auth/callback` **200** |

Email confirmation remains enabled. Security controls unchanged.

---

## 1. Exact Supabase Auth response (safe metadata)

| Recipient class | HTTP | Body (safe) |
|-----------------|------|-------------|
| Undeliverable (`@example.com`) | **500** | `error_code=unexpected_failure`, `msg=Error sending confirmation email` |
| Deliverable | **200** | User created; `confirmation_sent_at` set |
| Existing email (anti-enumeration) | **200** | `identities: []` |

Dashboard may label related failures as **422**; live GoTrue for confirmation-email failure returned **500**. Both mapped.

---

## 2. Classification

| Hypothesis | Verdict |
|------------|---------|
| Invalid email / payload | **No** for normal addresses |
| Password validation | **No** |
| Existing account | GoTrue empty `identities` → mapped to `email_already_registered` |
| Rate limiting | **No** in these probes |
| SMTP / Resend | Historical blocker; **working** for Auth SMTP from `no-reply@auth.quantforg.com` |
| Callback | Hash tokens on `/auth/callback` (and `/` bridge) — **fixed and verified** |

---

## 3. Resend / SMTP (no secrets)

| Check | Result |
|-------|--------|
| Sender | `"QuantForg" <no-reply@auth.quantforg.com>` |
| Subject | `Confirm your QuantForg email` |
| Domains | Owner-verified `auth.quantforg.com` + `quantforg.com` |
| Railway `RESEND_API_KEY` | Present (length only; not logged) |

Do **not** disable email confirmation.

---

## 4. Production frontend API config (after promotion)

| Item | Live |
|------|------|
| Same-origin API | `https://www.quantforg.com/qf-api/api/v1` via Next rewrite |
| `/qf-api/health` | **200** → Railway tip `c904fd0b` |
| Baked fallback | `NEXT_PUBLIC_API_BASE_URL` still Railway; runtime prefers `/qf-api` on QF hosts |

---

## 5. Why UI showed `Authentication failed` (historical)

Unmapped GoTrue confirmation-email / empty-identities failures on pre-`c904fd0b` Railway tip collapsed to generic `authentication_failed`. Fixed in #278.

---

## 6. Code fixes (merged in #278)

1. `auth_email_delivery_failed` (503) for confirmation-email send failures.  
2. Empty signup `identities` → `email_already_registered` (409).  
3. `EmailConfirmHashBridge` on `/` + hash handling on `/auth/callback`.  
4. Same-origin `/qf-api` rewrite + runtime API base.  
5. Email confirmation left enabled.

---

## 7. API E2E (Railway — retained)

| Step | Evidence |
|------|----------|
| Register | **201** |
| Error mapping | `@example.com` → **503** `auth_email_delivery_failed`; duplicate → **409** |
| Login after confirm | **200** |

---

## 8. Deploy timeline

| Event | Status |
|-------|--------|
| PR #278 merge | **MERGED** → `c904fd0b` |
| Railway | Live on `c904fd0b` |
| Vercel new Production build | **Rate-limited** |
| Vercel alias of Ready #278 preview → www/apex | **PASS** |
| Browser auto-login | **PASS** |

---

## 9. `ite_ops_alerts` (separate)

Null `id` constraint noise is unrelated to Auth. **No change**.
