# Live Market Chat — Phase Close (2026-11-10)

**Status: CLOSED**

## Scope closed

Public Live Market Chat (schema, RLS, API, frontend public surface, staging
authenticated acceptance, production Realtime publication).

## Identifiers

| Item | Value |
|---|---|
| Production Supabase | `otqyhlmwaifokrczryrc` |
| Staging Supabase | `saxsyobktmlyjghumxfz` |
| Chat migrations | `20261110180000`, `20261110180100`, `20261110180200` |
| Staging acceptance merge | PR #230 → `9a1d02948324050d9d881b4a7d9d3648fa288b0b` |
| Production Realtime apply | `20261110180200` applied + migration history repaired |
| Production API | `https://quantforg-production.up.railway.app` |
| Public Live page | `https://www.quantforg.com/live` |

## Staging authenticated evidence (PR #230)

- A/B disposable identities on staging only (`@example.com`)
- Session-bound author ID, spoof denied, cross-user UPDATE/DELETE denied
- Validation + rate limit + moderation/report authorization
- Realtime INSERT fanout on `acceptance_test`
- Cleanup emptied `acceptance_test`; disposable users deleted

## Production verification (this closeout)

- Additive Realtime publication for `live_market_chat_messages`
- Physical backups present (WAL-G); PITR not enabled (accepted for additive-only change)
- Anonymous public read PASS; anonymous writes/reports denied PASS
- Authenticated production write **not exercised** (no approved production test identity)
- Cross-user authorization relies on staging PASS + production RLS equivalence
- `/live` loads XAUUSD delayed reference price; chat empty-state; Send disabled when anonymous
- LIVE submit gates remain false; staging/prod isolation preserved

## Explicitly untested in production

- Authenticated POST/report against production identities
- Cross-user mutation against production rows
- Production websocket fanout with a live insert (publication membership verified; insert not performed)

## Handoff — next QuantForg phase

Live Market Chat is accepted and frozen for further feature work unless a
verified production bug, a11y/responsive/perf issue, or owner-authorized change
appears. Prefer the next planned multi-account / dispatch / eligibility work
already landing on `main` (post-#229) over additional chat chrome.
