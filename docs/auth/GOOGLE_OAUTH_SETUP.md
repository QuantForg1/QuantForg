# Google OAuth setup (QuantForg)

Code-side Google sign-in is implemented:

- Frontend button: `frontend/src/components/auth/google-auth-note.tsx`
- Callback page: `frontend/src/app/auth/callback/page.tsx`
- API: `GET /api/v1/auth/oauth/google` and `POST /api/v1/auth/oauth/callback`
- Kill switch: Railway `AUTH_OAUTH_ENABLED=true` (default true in settings)

Google will **not** work in production until the external dashboards below are configured. Do not invent Client IDs or secrets in the repository.

## 1. Google Cloud Console

1. Create (or open) an OAuth 2.0 Client ID of type **Web application**.
2. Authorized JavaScript origins:
   - `https://www.quantforg.com`
   - `https://quantforg.com`
   - local: `http://localhost:3000`
3. Authorized redirect URIs must include the **Supabase Auth callback**, not only the Next.js page:
   - `https://<YOUR_SUPABASE_PROJECT_REF>.supabase.co/auth/v1/callback`
4. Copy the Client ID and Client Secret into Supabase (next step). Never commit them.

## 2. Supabase Dashboard

1. Authentication → Providers → **Google** → Enable.
2. Paste Google Client ID + Client Secret.
3. Authentication → URL configuration:
   - **Site URL:** `https://www.quantforg.com`
   - **Redirect URLs** (add all that apply):
     - `https://www.quantforg.com/auth/callback`
     - `https://quantforg.com/auth/callback`
     - `http://localhost:3000/auth/callback`
     - password reset: `https://www.quantforg.com/reset-password`

## 3. Railway (API)

Confirm:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_ANON_KEY`
- `AUTH_REDIRECT_URL=https://www.quantforg.com/auth/callback`
- `AUTH_OAUTH_ENABLED=true`
- CORS includes `https://www.quantforg.com` (and apex)

No Google client secret belongs on Vercel or in `NEXT_PUBLIC_*` variables. The browser talks to Railway; Railway/Supabase talk to Google.

## 4. Vercel (frontend)

- `NEXT_PUBLIC_API_BASE_URL` → Railway `/api/v1`
- `NEXT_PUBLIC_APP_URL=https://www.quantforg.com`

## 5. Verification checklist

1. Open `/login` → **Continue with Google** redirects to Google (not a disabled stub).
2. Approve → land on `/auth/callback` → session restored → `/dashboard`.
3. Cancel Google consent → recoverable error + link back to `/login`.
4. Email/password login and forgot-password still work.
5. If Google provider is missing in Supabase, the UI shows a clear configuration error and does not claim success.

## Status language

Until steps 1–3 are completed in the live projects, report Google OAuth as **code-ready, provider configuration pending** — never as fully production-verified.
