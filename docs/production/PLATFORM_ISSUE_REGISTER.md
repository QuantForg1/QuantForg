# QuantForg platform issue register

Opened 16 Nov 2026 (session 5). Evidence comes from Production logs, Railway deployments, Supabase and the repository as of `e8c9997`. Each row records a status: **FIXED** (with its PR), **OPEN**, or **OWNER** (needs an owner action).

## Critical

| ID | Issue | Evidence | Status |
|---|---|---|---|
| C1 | API froze ~3 min after every deploy: `/health/live` returned 499 and login took up to 104 s | Railway http logs 20:12–20:14 UTC; three startup recovery steps read broker history synchronously on the event loop | **FIXED #325** (health ≤ 9 s during the next restart, 3–12 ms after) |
| C2 | Login timeouts | Broker reads shared the default thread pool with Supabase auth; login 8.7 s, refresh 3.2 s, `/auth/me` 1–1.6 s on every request | **FIXED #322** (separate pools; 20 s per-token user cache; logout evicts) |
| C3 | `/history/deals` hangs on the Windows gateway | Every call times out | **OWNER A1** (redeploy gateway `a150730e`). Contained by #307/#319/#326 |
| C4 | Owner-only risk policy visible to customers | RCC card, Overview order ticket, risk bounds API | **FIXED #323** (UI removed, API omits ceilings, activity reasons categorized; server enforcement unchanged) |

## High

| ID | Issue | Evidence | Status |
|---|---|---|---|
| H1 | RCC "Your accounts: Loading" / unknown status | Accounts waited on a 60 s gateway call | **FIXED #322/#323** (concurrent loads, 6 s evidence cap, UNAVAILABLE state) |
| H2 | RCC showed RUNNING from a default control value | `robot_state` defaulted to RUNNING | **FIXED #323** (RUNNING only with control + ROBOT_READY + subscription + submit path enabled) |
| H3 | History/Portfolio answered 500 for hours, then 503 only after 40–66 s | Railway http logs | **FIXED #319** (503) and **#326** (15 s history timeout) |
| H4 | Operator alerts never persisted; Telegram not delivered | `ite_ops_alerts` 0 rows ever; `telegram_configured=False` | Persistence **FIXED** (migration `20261116185523`); delivery **OWNER A11** |
| H5 | No Production worker supervisor, so no customer can trade | 0 workers, 0 hosts | **OWNER A5** |
| H6 | No DEMO acceptance evidence | 0 DEMO accounts | **OWNER A7, A4** |

## Medium

| ID | Issue | Status |
|---|---|---|
| M1 | 196 app routes but only about 16 customer desks in the rail; many legacy/ops pages are reachable by URL | OPEN: audit and retire pages that are not in nav or admin (needs a route-by-route pass with a signed-in session) |
| M2 | Owner risk constants still ship in the client bundle (owner ticket chunk) even though customers never load it | OPEN: move the ticket pre-check to the server-only `/execution/check` |
| M3 | Mobile shell: drawer scroll bleed; content under the tab bar | **FIXED #324**; full visual pass needs a signed-in browser session (OWNER A12) |
| M4 | Open-position `open_time` and candle times are raw broker server time (UTC+2) | OPEN |
| M5 | No external uptime monitor on the gateway | OPEN |
| M6 | Owner cannot see the gateway's deployed SHA (`/health` has none) | OPEN: add the commit to gateway `/health` in the next gateway release |

## Low / cosmetic

| ID | Issue | Status |
|---|---|---|
| L1 | `test_liveness` is flaky under xdist | OPEN |
| L2 | 2 pre-existing mypy errors (missing `score_calibration_audit`) | OPEN |
| L3 | Control-state label said "Running" for a setting | **FIXED #323** (now "Enabled"; real status separate) |

## Owner actions (only the owner can do these)

A1 gateway redeploy · A4 DEMO commissions · A5 worker supervisor · A6 leaked-password toggle · A7 three DEMO users · A8 restore drill approval · A9 GitHub Pro · A10 NOWPayments approval · A11 `TELEGRAM_OPERATOR_CHAT_ID` · **A12 (new): sign in once in the Claude desktop app's built-in browser**, so authenticated pages can be checked on mobile and desktop without sharing a password.
