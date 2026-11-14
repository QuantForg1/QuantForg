# Eight-broker Production acceptance (2026-11-14)

**Production SHA (pre-this-PR):** `1e75cdf371fbf6bbf098fd29b576661d3f574faa` (PR #249)  
**Host health:** `https://quantforg-production.up.railway.app/api/v1/health` → `status=ok`  
**Orders submitted during acceptance:** **0**  
**Global execution:** **OFF** (`MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`)

## Acceptance matrix

| Broker | MT5 Connected | Trading Permission | Risk Controls | Kill-Switch | Acceptance |
|---|---|---|---|---|---|
| Weltrade | YES | YES (`trade_allowed=true`) | PASS | PASS (global OFF) | **PASS** |
| XM | YES | YES | PASS | PASS | **PASS** |
| Exness | YES | NO (`authenticated_trading_not_enabled`) | PASS | PASS | **CONDITIONAL** |
| HFM | YES | NO (`authenticated_trading_not_enabled`) | PASS | PASS | **CONDITIONAL** |
| JustMarkets | YES | NO (`authenticated_trading_not_enabled`) | PASS | PASS | **CONDITIONAL** |
| IC Markets | YES | YES | PASS | PASS | **PASS** |
| Pepperstone | YES | YES | PASS | PASS | **PASS** |
| FP Markets | YES | YES | PASS | PASS | **PASS** |

**Fleet fully accepted:** NO (5/8 trading-permission PASS).

## Blockers (exact) — rechecked 2026-11-14 ~13:20 local

Portable `demo-a` LIVE re-verify (master password from local.env; Program Files Weltrade untouched):

| Broker | Server | Login mask | `trade_mode` | Balance | `trade_allowed` | Error |
|---|---|---|---|---|---|---|
| Exness | `Exness-MT5Real10` | `***6277` | 2 | **0.00** | false | `authenticated_trading_not_enabled` |
| HFM | `HFMarketsGlobal-Live20` | `***2172` | 2 | **0.00** | false | `authenticated_trading_not_enabled` |
| JustMarkets | `JustMarkets-Live7` | `***0106` | 2 | **0.00** | false | `authenticated_trading_not_enabled` |

Root cause: accounts authenticate on the correct LIVE servers with hedge `trade_mode=2`, but MT5 reports trading disabled with **zero balance**. This is a broker funding/activation restriction — not an adapter bug, wrong server, or investor-password session. Owner must fund/activate at each broker, then re-run portable verify until `trade_allowed=true`.

**Catalogue honesty:** `trade_allowed` / `trading_enabled` are **not** manufactured for these three. Verified + connectable display may remain; trading permission stays false until MT5 agrees.

## Risk & kill-switch

- Global submit remains OFF; `FORCE_FIRST_TRADE=false`; `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.
- Dry-run / eligibility paths do not call OMS `order_send`.
- Weltrade Program Files LIVE terminal protected.

## Global execution decision

**Not enabled.** Gate requires genuine MT5 `trade_allowed=true` for all eight brokers.

## Server discovery (this PR)

Expanded genuine MT5-observed candidates in `mt5_ecosystem.py` (Weltrade Real/Demo, XMGlobal-MT5 N, Exness Real/Trial N, plus verified LIVE servers). Manual portal paste retained. No invented shards. See `docs/architecture/MT5_SERVER_DISCOVERY.md`.

## Distilled summary

1. **Runtime MT5 connected (8/8)**  
2. **Confirmed trading permission (5/8)** — weltrade, xm, ic-markets, pepperstone, fp-markets  
3. **Exness / HFM / JustMarkets:** auth OK, balance 0, `trade_allowed=false`  
4. **Risk / kill-switch:** global submit OFF  
5. **Global execution enabled:** NO  
6. **Real orders during acceptance:** none  
