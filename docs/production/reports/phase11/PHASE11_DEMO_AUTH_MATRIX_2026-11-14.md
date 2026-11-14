# Phase 11 — Portable DEMO authentication matrix (2026-11-14)

**Slot:** `demo-a` only (soft cap 1).  
**Mode:** DEMO verify only.  
**Staging dispatch:** NOT enabled.  
**Production multi-account LIVE:** NOT touched.  
**Weltrade Program Files LIVE:** protected / outside portable budget.

## Preconditions

| Check | Result |
|---|---|
| `local.env` gitignored | PASS (`.gitignore:279`) |
| Credential presence (8/8 demo triples) | PASS — `blocked:0` via `check_broker_credentials.ps1` (values not printed) |
| Pepperstone login whitespace in file | Fixed (leading tab stripped; values not printed) |
| `QUANTFORG_API_BASE_URL` | staging host `quantforg-staging.up.railway.app` · https |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` |
| `WORKER_SERVICE_TOKEN` | set · length ≥ 16 (value not printed) |

## Authentication results (real MT5)

Evidence: `var/mt5_broker_verification.json` · source `windows_mt5_demo_verify`.

| Broker | Server (observed) | Login masked | trade_allowed | market_data_ok | Claim |
|---|---|---|---|---|---|
| weltrade | Weltrade-Demo | `***0953` | true | true | **DEMO VERIFIED** |
| xm | XMGlobal-MT5 2 | `***0464` | true | true | **DEMO VERIFIED** |
| exness | Exness-MT5Trial9 | `***6227` | true | true | **DEMO VERIFIED** |
| hfm | HFMarketsGlobal-Demo | `***3676` | true | true | **DEMO VERIFIED** |
| justmarkets | JustMarkets-Demo | `***0008` | true | true | **DEMO VERIFIED** |
| ic-markets | ICMarketsSC-Demo | `***8224` | true | true | **DEMO VERIFIED** |
| pepperstone | Pepperstone-Demo | `***5669` | true | true | **DEMO VERIFIED** |
| fp-markets | — | — | — | — | **NOT VERIFIED** — `initialize_failed:(-10005, 'IPC timeout')` (retry same error) |

**Score:** 7 / 8 DEMO VERIFIED. FP Markets remains blocked on portable IPC timeout (not claimed verified).

## Safety

- Orders submitted: **0**
- Staging `MULTI_ACCOUNT_DISPATCH_ENABLED`: **unchanged / not enabled by this run**
- Production LIVE multi-account: **unchanged**

## Security note

Demo credential material was pasted into chat during this session. Prefer rotating those demo passwords in broker portals and updating protected `local.env` offline. Do not commit `local.env`.
