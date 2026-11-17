# QuantForg platform issue register

Opened 16 Nov 2026 (session 5). Evidence comes from Production logs, Railway deployments, Supabase and the repository as of `e8c9997`. Each row records a status: **FIXED** (with its PR), **OPEN**, or **OWNER** (needs an owner action).

## Critical

| ID | Issue | Evidence | Status |
|---|---|---|---|
| C1 | API froze ~3 min after every deploy: `/health/live` returned 499 and login took up to 104 s | Railway http logs 20:12–20:14 UTC; three startup recovery steps read broker history synchronously on the event loop | **FIXED #325** (health ≤ 9 s during the next restart, 3–12 ms after) |
| C1b | Event loop blocked 7–45 s by sync gateway calls in async handlers and the ITE loop | Watchdog stacks (21:23–21:52 UTC) | **FIXED #328, #330, #331** (guard test + watchdog stay on) |
| C2 | Login timeouts | Broker reads shared the default thread pool with Supabase auth; login 8.7 s, refresh 3.2 s, `/auth/me` 1–1.6 s on every request | **FIXED #322** (separate pools; 20 s per-token user cache; logout evicts) |
| C3 | `/history/deals` hangs on the Windows gateway | Every call times out | **OWNER A1** (redeploy gateway `a150730e`). Contained by #307/#319/#326 |
| C4 | Owner-only risk policy visible to customers | RCC card, Overview order ticket, risk bounds API | **FIXED #323** (UI removed, API omits ceilings, activity reasons categorized; server enforcement unchanged) |

| C5 | 97 routers had session-only auth: any user could change platform-wide state | Code audit 17 Nov | **FIXED #333** (63 routers owner/admin; per-endpoint gates; test `test_operator_api_rbac.py`) |

| C6 | Customer could switch the shared platform terminal (owner LIVE session logged out) | Incident 16 Nov 23:46 UTC | **FIXED #340/#341**; owner restore pending (A13) |

| C8 | Signed-in users could write ~60 tables directly via Supabase REST (anon key + their JWT): own `licenses`, `broker_accounts`/`mt5_connections` (register any MT5 login), `users`, `audit_logs`, `user_risk_settings`, billing rows | RLS audit 17 Nov 01:15 UTC: policies `*_insert_own`/`*_update_own` + table grants to `authenticated` | **FIXED** migrations `20261117011925`, `20261117012014`: all INSERT/UPDATE/DELETE/TRUNCATE revoked from `authenticated`/`anon` on every public table and in default privileges; SELECT stays under RLS. Frontend uses no supabase-js; backend writes with service role / direct Postgres. API verified 200s after the change |

| C9 | Owner risk policy (and all public tables) readable via Supabase REST | RLS audit 17 Nov | **FIXED** migration `20261117013324` |
| C10 | Any user could submit/cancel/manage orders on the shared owner terminal | API write-path audit 17 Nov | **FIXED #349** |
| C11 | Customer could arm/disarm broker-wide or owner-armed emergency stops | API write-path audit 17 Nov | **FIXED #349** |
| C12 | LIVE robot auto-resumed after restart once inside session (would have resumed 07:00 UTC 17 Nov) | Prod log `live_trading_safe_recovery_blocked failures=[outside_session]` | **FIXED #350/#351**; owner pause applied 02:11:39 |
| H-BAL | Broker page balance/equity "—": `/portfolio` 503 on gateway history circuit | Prod 02:12 | **FIXED #352/#353** (1–2 s, verified) |

## High

| ID | Issue | Evidence | Status |
|---|---|---|---|
| H1 | RCC "Your accounts: Loading" / unknown status | Accounts waited on a 60 s gateway call | **FIXED #322/#323** (concurrent loads, 6 s evidence cap, UNAVAILABLE state) |
| H2 | RCC showed RUNNING from a default control value | `robot_state` defaulted to RUNNING | **FIXED #323** (RUNNING only with control + ROBOT_READY + subscription + submit path enabled) |
| H3 | History/Portfolio answered 500 for hours, then 503 only after 40–66 s | Railway http logs | **FIXED #319** (503) and **#326** (15 s history timeout) |
| H4 | Operator alerts never persisted; Telegram not delivered | `ite_ops_alerts` 0 rows ever; `telegram_configured=False` | Persistence **FIXED** (migration `20261116185523`); delivery **OWNER A11** |
| H5 | No Production worker supervisor, so no customer can trade | 0 workers, 0 hosts | **OWNER A5** |
| H6 | No DEMO acceptance evidence | 0 DEMO accounts | **OWNER A7, A4** |

| H7 | Live crypto checkout open before provider approval | **FIXED #346** (closed by default; owner opens with `BILLING_LIVE_CHECKOUT_ENABLED`) |
| C7 | Owner execution identity re-pointed to a customer login by auto-adoption | **FIXED #343** (registered-login rule; verified in Production logs) |

## Medium

| ID | Issue | Status |
|---|---|---|
| M1 | 336 page files (customers: 31) | **MITIGATED #333** (customer route boundary + `ROUTE_REGISTER.md`); retirement of 112 unlinked pages needs owner confirmation |
| M1-old | 196 app routes but only about 16 customer desks in the rail; many legacy/ops pages are reachable by URL | OPEN: audit and retire pages that are not in nav or admin (needs a route-by-route pass with a signed-in session) |
| M2 | Owner risk constants still ship in the client bundle (owner ticket chunk) even though customers never load it | OPEN: move the ticket pre-check to the server-only `/execution/check` |
| M3 | Mobile shell: drawer scroll bleed; content under the tab bar | **FIXED #324**; full visual pass needs a signed-in browser session (OWNER A12) |
| M4 | Open-position `open_time` and candle times are raw broker server time (UTC+2) | OPEN |
| M5 | No external uptime monitor on the gateway | OPEN |
| M6 | Owner cannot see the gateway's deployed SHA (`/health` has none) | OPEN: add the commit to gateway `/health` in the next gateway release |

| M7 | API region (SFO) far from Supabase (eu-central-1), gateway and users | **FIXED**: moved to europe-west4 (latency −35–75 %) |
| M8 | Customer pages contain technical copy (e.g. Book: "nulls when data unavailable · no fabricated zeros"); Dashboard waits on slow session reads | OPEN |

## Low / cosmetic

| ID | Issue | Status |
|---|---|---|
| L1 | `test_liveness` is flaky under xdist | OPEN |
| L2 | 2 pre-existing mypy errors (missing `score_calibration_audit`) | OPEN |
| L3 | Control-state label said "Running" for a setting | **FIXED #323** (now "Enabled"; real status separate) |

## Owner actions (only the owner can do these)

A1 gateway redeploy · A4 DEMO commissions · A5 worker supervisor · A6 leaked-password toggle · A7 three DEMO users · A8 restore drill approval · A9 GitHub Pro · A10 NOWPayments approval · A11 `TELEGRAM_OPERATOR_CHAT_ID` · **A12 (new): sign in once in the Claude desktop app's built-in browser**, so authenticated pages can be checked on mobile and desktop without sharing a password.
