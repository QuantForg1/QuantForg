# Live Market Chat — owner-controlled test identities

## Phase status

**CLOSED (2026-11-10).** See `docs/ops/LIVE_MARKET_CHAT_PHASE_CLOSE.md`.

Authenticated write-path acceptance completed on **QuantForg-Staging**
(`saxsyobktmlyjghumxfz`) with disposable identities and channel
`acceptance_test` only. Production authenticated write was intentionally
**not** exercised (no approved production test identity).

## Why this exists

Authenticated Live Market Chat write-path acceptance requires **two disposable,
non-production identities** restricted to channel `acceptance_test`.

Automated unit/RLS/failover coverage is green (PR #223 / #225 / #226).
Live authenticated posts must not use the production owner account.

## Current inventory (as of 2026-11-10 closeout)

| Surface | Finding |
|---|---|
| Production Supabase | `QuantForg` / `otqyhlmwaifokrczryrc` |
| Staging Supabase | `QuantForg-Staging` / `saxsyobktmlyjghumxfz` |
| Railway staging | Bound to staging Supabase only |
| Chat migrations on production | `20261110180000`, `20261110180100`, `20261110180200` (history repaired) |
| Production Realtime | `live_market_chat_messages` in `supabase_realtime` |
| Disposable staging identities | Provisioned for acceptance, then deleted |
| Approved production test identity | **None** — do not invent |

## Owner procedure (future QA only)

### Staging (preferred)

1. Use project `QuantForg-Staging` (`saxsyobktmlyjghumxfz`).
2. Ensure migrations through `20261110180200` are applied.
3. Railway staging must use staging `SUPABASE_URL` / anon / service-role only.
4. Provision two disposable `@example.com` users via Auth Admin on staging.
5. Store locally only:
   - `QF_CHAT_ACCEPT_A_EMAIL` / `QF_CHAT_ACCEPT_A_PASSWORD`
   - `QF_CHAT_ACCEPT_B_EMAIL` / `QF_CHAT_ACCEPT_B_PASSWORD`
   - `QF_CHAT_ACCEPT_API_BASE` = staging API `…/api/v1`
6. Authorize posts **only** to channel `acceptance_test`.

### Production exception

Requires explicit owner-signed approval. Default remains **do not** create
production chat acceptance users.

## Acceptance exercises (staging)

All posts must use `channel=acceptance_test` (never public `xauusd`).

1. Login A → `POST /market/chat` succeeds; response `user_id` matches session.
2. Spoof body fields cannot change `user_id`.
3. Empty / oversized / control-only bodies rejected.
4. Burst posts → `rate_limited`.
5. `POST /market/chat/{id}/report` requires auth; works for A.
6. With B: cross-user UPDATE/DELETE via PostgREST denied by RLS.
7. Anon read works; anon write still 401.
8. Realtime INSERT fanout observed for staging publication.

## Cleanup

1. Delete acceptance rows on staging `acceptance_test`.
2. Delete disposable Auth + `public.users` rows on staging.
3. Unset local `QF_CHAT_ACCEPT_*` secrets.
4. Confirm channel count is 0.

## Safety invariants (unchanged)

- `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`
- `QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`
- `FORCE_FIRST_TRADE=false`
- `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` unset/false by default
- No LIVE orders; Weltrade / Robot / OMS / Trading Core untouched
- Never print passwords, service-role keys, or access tokens in reports
