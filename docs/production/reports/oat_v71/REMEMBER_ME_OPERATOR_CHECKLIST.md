# Remember Me — operator validation checklist (OAT Step 4)

Generated: 2026-07-29T01:20Z

## Software status

Auth persistence design (unchanged contract):

- Remember Me ON → `localStorage` (`qf_access_token`, `qf_refresh_token`, `qf_user`, `qf_remember_me=1`)
- Remember Me OFF → `sessionStorage` only
- Agent browser profiles without a prior login **cannot** prove this gate

Fix applied for a verified soft defect:

- Token refresh now preserves Remember Me preference via `isRememberMeEnabled()` in
  `frontend/src/lib/api/client.ts` when calling `saveSession` (avoids forcing localStorage
  on refresh when the operator chose session-only).

The earlier OAT FAIL (agent browser at `/login`) is **expected for a clean automation profile**, not proof that production Remember Me is broken.

## Operator steps (required for PASS)

Use the **real operator browser profile** that signs into production:

1. Open `https://www.quantforg.com/login`
2. Sign in with **Remember me** checked
3. Confirm redirect to `/terminal` (or app shell) while authenticated
4. Hard refresh (Ctrl+F5) — must stay signed in
5. Close the browser completely and reopen the same profile — must stay signed in
6. **Restart the PC**, reopen the same browser profile, open `https://www.quantforg.com/` — must stay signed in without login form
7. Confirm broker workspace can restore from encrypted profile (no manual password re-entry if profile present)

## Evidence to save

Write results under `docs/production/reports/oat_v71/`:

- `step4_remember_me_refresh.json` — timestamp, URL after refresh, authenticated true/false
- `step4_remember_me_browser_reopen.json` — same after full browser restart
- `step4_remember_me_pc_restart.json` — same after PC restart
- Optional screenshots

## Gate rule

OAT Step 4 = **PASS** only when steps 4–7 succeed with evidence files present.  
Until then: **PAT/OAT remain NOT ACCEPTED**; do not push production release to `main`.
