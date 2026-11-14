# PHASE — Registration API Connectivity

**Date:** 2026-11-14  
**Branch:** `fix/registration-api-connectivity`  
**Production frontend:** https://www.quantforg.com/register  
**Railway API:** https://quantforg-production.up.railway.app  

| Gate | Status |
|------|--------|
| Frontend → Railway reachability (browser) | **PASS** |
| CORS preflight / POST `Access-Control-Allow-Origin` | **PASS** |
| `NEXT_PUBLIC_API_BASE_URL` baked into Production bundle | **PASS** (`…/api/v1`) |
| Registration end-to-end account create | **BLOCKED** — Supabase Auth signup HTTP **500** |
| Confirmation email (Resend/SMTP) | **BLOCKED** — cannot verify until signup 500 clears |
| Vercel deploy of this fix | **PENDING** / may be rate-limited |

---

## 1. Actual failed endpoint

| Layer | Endpoint | Observed |
|-------|----------|----------|
| Browser → API | `POST https://quantforg-production.up.railway.app/api/v1/auth/register` | Reachable; returns **401** JSON |
| API → Supabase | `POST https://otqyhlmwaifokrczryrc.supabase.co/auth/v1/signup` | **HTTP/2 500 Internal Server Error** |

Example request id: `req_f84e332ccf3d4379ad6c695cd8269f2e` / `req_417b0b74e0374dbdaa076c344b3997fa`.

Visible toast **"Unable to reach the QuantForg API…"** is the client `network_error` path (`frontend/src/lib/api/client.ts`). In this investigation the Production browser **did** complete `fetch` to Railway (health/live 200; register 401). Intermittent client DNS to `*.up.railway.app` was also observed (`curl: (6) Could not resolve host`), which explains genuine network toasts for some users/networks.

---

## 2. Root cause

**Primary (registration cannot succeed):** Supabase Auth `/auth/v1/signup` returns **500**. Railway maps that to `authentication_failed` / HTTP 401 with public message `"Authentication failed"`. Users are not created; no confirmation email can be sent until Auth signup succeeds.

**Secondary (connectivity UX):** Cross-origin dependence on `quantforg-production.up.railway.app` DNS can fail intermittently from some clients, surfacing as `API_UNREACHABLE` even when Railway itself is healthy.

**Not the cause:** Wrong `NEXT_PUBLIC_API_BASE_URL` in the live bundle (verified baked value is Railway `/api/v1`). CORS for `https://www.quantforg.com` allows POST/OPTIONS.

---

## 3. Frontend API base URL before / after

| | Value |
|--|--------|
| **Before (live bundle)** | `https://quantforg-production.up.railway.app/api/v1` |
| **After (browser on www/apex)** | `https://www.quantforg.com/qf-api/api/v1` via Next rewrite → Railway |
| **After (SSR / non-QF hosts)** | Unchanged configured `NEXT_PUBLIC_API_BASE_URL` |

Vercel Production already defines `NEXT_PUBLIC_API_BASE_URL` (secret type) and `NEXT_PUBLIC_APP_URL`.

---

## 4. CORS findings

| Check | Result |
|-------|--------|
| OPTIONS `/api/v1/auth/register` Origin `https://www.quantforg.com` | **200**; `access-control-allow-origin: https://www.quantforg.com`; methods include POST; credentials true |
| POST response ACAO | Present on 401/422 responses |

No CORS change required for www. Same-origin `/qf-api` proxy further reduces CORS surface for browsers.

---

## 5. Railway response

- `GET /health` → 200 `{"status":"ok","commit":"41bc970…"}`  
- `POST /api/v1/auth/register` (valid JSON body) → **401**  
  `{"error":{"code":"authentication_failed","message":"Authentication failed","details":{}}}`  
- Duration ~3–7s while waiting on Supabase.

---

## 6. Supabase Auth response

- `POST …/auth/v1/signup` → **500 Internal Server Error** (logged by Railway httpx).  
- Most likely classes: Auth email/SMTP misconfiguration (e.g. Resend), project Auth outage, or Auth hook failure.  
- **Owner action:** Supabase Dashboard → Authentication → SMTP / Providers; confirm Resend host, port, user, password, sender domain verification; inspect Auth logs for the 500 body. Do not disable email confirmation to bypass.

---

## 7. SMTP delivery result

**BLOCKED / not verified.** No confirmation email can be asserted while signup returns 500. Resend must be validated in Supabase SMTP settings after Auth signup returns 2xx / creates the user.

---

## 8. Registration end-to-end result

| Step | Result |
|------|--------|
| Frontend sends register | **PASS** (correct path + payload) |
| Railway receives | **PASS** |
| Supabase creates user | **FAIL** (500) |
| Profile provisioning | Not reached |
| Confirmation email | Not reached |
| Confirm callback → Production | Not reached |
| Sign-in | Not reached |

---

## 9. Code fixes in this phase

1. Remove `middleware.ts` / keep OAuth `/?code=` forward in `proxy.ts` (Next.js 16 forbids both — was breaking Production build).  
2. Next rewrite `/qf-api/:path*` → Railway origin.  
3. `getRuntimeApiBaseUrl()` prefers same-origin proxy on Production hosts.  
4. Map Supabase HTTP 5xx → `auth_provider_error` / **503** with actionable public message (not generic 401 Authentication failed).  
5. Detect `response.error` on sign_up when GoTrue returns soft failures.

---

## 10. Vercel deployment SHA

| Item | Value |
|------|-------|
| PR | *filled after create* |
| Deploy | **BLOCKED** if Vercel rate limit persists — do not claim live until SHA verified on www |

---

## 11. Remaining blockers

1. **Supabase Auth signup 500** — Owner must repair Auth/SMTP (Resend) until `/auth/v1/signup` succeeds.  
2. **Vercel deploy rate limit** (if still active) — retry normal deploy workflow.  
3. Re-test confirmation email delivery only after (1) is green.

**Do not mark complete based on `/health` alone.** Health PASS does not equal registration PASS.
