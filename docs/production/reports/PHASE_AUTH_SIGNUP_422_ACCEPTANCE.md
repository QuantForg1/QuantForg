# PHASE — Production Signup HTTP 422 / Confirmation Email

**Date:** 2026-11-14  
**Branch:** `fix/registration-api-connectivity`  
**PR:** https://github.com/QuantForg1/QuantForg/pull/278  

| Gate | Status |
|------|--------|
| Exact Auth error metadata captured | **PASS** |
| Root cause classified | **PASS** (see §2) |
| Signup creates user (deliverable email) | **PASS** (Railway `201`) |
| Confirmation email → Resend | **PASS** (`last_event: delivered` on prior Gmail probe) |
| Confirm verify + login | **PASS** |
| Specific UI/API errors (mapping) | **PASS** on Railway tip `c904fd0b` |
| `/qf-api` same-origin proxy on www | **BLOCKED** — Vercel Production promote rate-limited |
| `ite_ops_alerts` null `id` | **SEPARATE** — not causing signup failure; no code change |

### Post-merge Production retest (2026-11-15)

| Check | Result |
|-------|--------|
| PR #278 | **MERGED** (`c904fd0b`) |
| Railway `/health` | `commit: c904fd0b…` |
| `@example.com` register | **503** `auth_email_delivery_failed` (specific message) |
| Duplicate register | **409** `email_already_registered` |
| Fresh Gmail register | **201** success message |
| www `/qf-api/health` | **404** — Production alias still on pre-#278 Vercel tip; promote blocked (`api-deployments-free-per-day`) |
| Browser register toast | Uses Railway `NEXT_PUBLIC_API_BASE_URL` today → **receives new public messages** without `/qf-api` |

---

## 1. Exact Supabase Auth response (safe metadata)

Direct `POST {SUPABASE_URL}/auth/v1/signup` (anon/publishable key):

| Recipient class | HTTP | Body (safe) |
|-----------------|------|-------------|
| Undeliverable / reserved (`@example.com`) | **500** | `error_code=unexpected_failure`, `msg=Error sending confirmation email`, `error_id=01a1dc70-…` / `01a1dc74-…` |
| Deliverable (`@gmail.com`, `@auth.quantforg.com`) | **200** | User created; `confirmation_sent_at` set |
| Existing email (anti-enumeration) | **200** | User-shaped payload with **`identities: []`** (no hard `email_exists`) |

Dashboard/logs may label related Auth failures as **422**; live GoTrue for the confirmation-email failure returned **500** with the `msg` above. Both are mapped in this PR.

Railway (pre-deploy tip `41bc970`) for `@example.com`:

```json
{"error":{"code":"authentication_failed","message":"Authentication failed","details":{}}}
```

That generic toast is **not** SMTP being “unknown” — it is unmapped Auth provider failure on the still-live tip.

---

## 2. Classification

| Hypothesis | Verdict |
|------------|---------|
| Invalid email / signup payload | **No** for normal addresses; payload accepted |
| Password validation | **No** |
| Existing account | **Partial** — GoTrue returns empty `identities` (200); live app remapped that to `identity_mismatch` / “Authentication failed” |
| Email rate limiting | **No** in these probes |
| SMTP delivery / Resend | **Was** the historical blocker; **now works** for deliverable inboxes from `no-reply@auth.quantforg.com` |
| Auth callback / redirect | Confirm links use Site URL + **hash tokens**; `/auth/callback` previously only handled OAuth `?code=` |

**Primary user-visible failure during SMTP outage:** GoTrue `Error sending confirmation email` → Railway `authentication_failed` → UI toast **Authentication failed**.

**Current Production happy path (API):** deliverable email → register `201` → Resend delivered → verify link confirms → login `200`.

---

## 3. Resend / SMTP (no secrets)

| Check | Result |
|-------|--------|
| Sender observed in Resend | `"QuantForg" <no-reply@auth.quantforg.com>` |
| Subject | `Confirm your QuantForg email` |
| Domains | Owner reports `auth.quantforg.com` + `quantforg.com` verified |
| Railway `RESEND_API_KEY` | Present (length recorded only; value not logged) |
| Recent Auth confirmations | `delivered` to Gmail probe; `sent` to `@auth.quantforg.com` probe |

Do **not** disable email confirmation. Prefer Resend SMTP password = API key; host `smtp.resend.com`; port **465** or **587** per Resend docs.

---

## 4. Production frontend API config

| Item | Live now | This PR |
|------|----------|---------|
| Register path | Browser → Railway `…/api/v1/auth/register` (baked `NEXT_PUBLIC_API_BASE_URL`) | Prefer `https://www.quantforg.com/qf-api/api/v1` rewrite |
| `/qf-api/health` | **404** (rewrite not on live Vercel tip) | Deploy required |
| CORS / Railway reachability | **PASS** | Unchanged |

---

## 5. Why UI shows `Authentication failed`

1. `error_handler` public map defaults unknown/`authentication_failed` → `"Authentication failed"`.  
2. Live Railway tip predates 5xx / confirmation-email mapping (`commit: 41bc970`).  
3. Register page already surfaces `ApiError.message` — so fixing the **backend code** fixes the toast.  
4. Duplicate signup empty-identities path incorrectly became `identity_mismatch` with the same generic message on live.

---

## 6. Fixes in this PR (additional)

1. Map `Error sending confirmation email` / related → `auth_email_delivery_failed` (503, specific public copy).  
2. Treat GoTrue signup `identities: []` as `email_already_registered` (409).  
3. Client `EmailConfirmHashBridge` on `/` + hash handling on `/auth/callback` for `#access_token&type=signup`.  
4. Keep email confirmation enabled.

---

## 7. E2E Production evidence (API / Resend)

| Step | Evidence |
|------|----------|
| Signup | Railway `POST /api/v1/auth/register` → **201** for `signup.prod+…@gmail.com` |
| User created | Supabase user id in signup response; profile login succeeded |
| Resend | Email id `01a1dc71-f213-…`, `last_event: delivered` |
| Confirm | `GET /auth/v1/verify?token=…&type=signup` → **303** to `https://www.quantforg.com#access_token=…&type=signup` |
| Sign-in | Railway `POST /api/v1/auth/login` → **200** with session |

Browser hash auto-login on `/` requires the frontend deploy of this PR.

---

## 8. PR #278 / deploy status

| Surface | Status |
|---------|--------|
| GitHub CI (Lint/Type/Unit/Trading/Frontend/Integration) | **SUCCESS** (prior head); re-run after this push |
| Mergeable | **MERGEABLE** (prior) |
| Vercel check | **FAILURE** — build rate-limit (`upgradeToPro=build-rate-limit`) |
| Railway live tip | `41bc970` — **not** yet this branch |
| Vercel www tip | Pre-`/qf-api` (404 on `/qf-api/health`) |

Verify Railway and Vercel **independently** after merge/deploy; do not treat CI green as Production green.

---

## 9. `ite_ops_alerts` (separate)

Null `id` constraint noise in Railway logs is unrelated to Auth signup (ITE operator alert persist path). **No change** in this PR without evidence it blocks registration.
