# Google OAuth setup (QuantForg)

Code-side Google sign-in is implemented:

- Frontend button: `frontend/src/components/auth/google-auth-button.tsx`
- Callback page: `frontend/src/app/auth/callback/page.tsx`
- API: `GET /api/v1/auth/oauth/google` and `POST /api/v1/auth/oauth/callback`
- Kill switch: Railway `AUTH_OAUTH_ENABLED=true` (default true in settings)

Do not invent Client IDs or secrets in the repository. Never put Google client secrets in Vercel or `NEXT_PUBLIC_*`.

## 1. Google Cloud Console

1. Create (or open) an OAuth 2.0 Client ID of type **Web application**.
2. Authorized JavaScript origins:
   - `https://www.quantforg.com`
   - `https://quantforg.com`
   - local: `http://localhost:3000`
3. Authorized redirect URIs must include the **Supabase Auth callback**, not only the Next.js page:
   - `https://otqyhlmwaifokrczryrc.supabase.co/auth/v1/callback`
4. Copy the Client ID and Client Secret into Supabase (next step). Never commit them.

## 2. Google Search Console — domain ownership (branding)

Google Cloud Branding / OAuth consent may report that `www.quantforg.com` / `quantforg.com` is **not verified as owned** by the Google account tied to the Cloud project. Until that is fixed, public brand verification can remain incomplete even when login works for the configured audience (e.g. Testing / Internal).

Exact steps:

1. Sign in to [Google Search Console](https://search.google.com/search-console) with a Google account that is an **Owner or Editor** on the same Cloud project used for OAuth.
2. Add a **Domain** property for `quantforg.com` (root domain — covers `www` and apex). Prefer Domain over URL-prefix so ownership covers all subdomains/protocols.
3. Verify ownership with the **DNS TXT** method (required for Domain properties):
   - Copy the TXT record Search Console shows.
   - Add it at your DNS provider for `quantforg.com`.
   - Wait for DNS propagation, then click **Verify** in Search Console.
4. Confirm the verified property appears as owned.
5. In Google Cloud Console → **Google Auth Platform / OAuth branding** (or OAuth consent screen):
   - Ensure **Authorized domains** includes `quantforg.com`.
   - Ensure homepage / privacy / terms URLs use that verified domain.
6. Only then submit / publish branding verification if you need the QuantForg name and logo on the public consent screen.

Until Search Console shows `quantforg.com` verified for the project account, report domain branding as **pending external verification** — do not claim public OAuth branding is complete.

Login can still work for allowed test users while branding verification is pending.

## 3. Supabase Dashboard

1. Authentication → Providers → **Google** → Enable.
2. Paste Google Client ID + Client Secret.
3. Authentication → URL configuration:
   - **Site URL:** `https://www.quantforg.com`
   - **Redirect URLs** (add all that apply):
     - `https://www.quantforg.com/auth/callback`
     - `https://quantforg.com/auth/callback`
     - `http://localhost:3000/auth/callback`
     - password reset: `https://www.quantforg.com/reset-password` (and `/forgot-password` if used)

## 4. Railway (API)

Confirm:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`
- `AUTH_REDIRECT_URL=https://www.quantforg.com/auth/callback`
- `AUTH_OAUTH_ENABLED=true`
- CORS includes `https://www.quantforg.com` (and apex)

## 5. Vercel (frontend)

- `NEXT_PUBLIC_API_BASE_URL` → Railway `/api/v1`
- `NEXT_PUBLIC_APP_URL=https://www.quantforg.com`

## 6. Verification checklist

1. Open `/login` → **Continue with Google** (no explanatory paragraph under the button).
2. API `GET /api/v1/auth/oauth/google?redirect_to=https://www.quantforg.com/auth/callback` returns a Supabase `…/auth/v1/authorize?provider=google…` URL.
3. Approve → land on `/auth/callback` → session restored → authenticated app surface.
4. Cancel Google consent → recoverable error + link back to `/login`.
5. Email/password login and forgot-password still work.
6. Search Console domain ownership verified if public branding is required.

## Status language

- **Provider configured:** production OAuth start returns a live Supabase Google authorize URL.
- **Interactive login:** confirm manually in a browser with an allowed test user.
- **Brand / domain ownership:** complete Search Console DNS verification above before claiming public branding is verified.
