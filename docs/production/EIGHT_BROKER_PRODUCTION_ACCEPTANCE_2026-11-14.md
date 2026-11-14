# Eight-broker Production acceptance (2026-11-14)

**Production SHA:** `1e75cdf371fbf6bbf098fd29b576661d3f574faa` (PR #249)  
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

## Blockers (exact)

Exness (`***6277` / `Exness-MT5Real10`), HFM (`***2172` / `HFMarketsGlobal-Live20`), and JustMarkets (`***0106` / `JustMarkets-Live7`) authenticate to the correct LIVE login/server with `trade_mode=2`, but MT5 reports **`trade_allowed=false`**. Typical cause: unfunded / trading not activated at the broker. Owner must fund/activate, then re-run portable verify until `trade_allowed=true`.

## Risk & kill-switch (Phase 2)

- Kill-switch arm/disarm: PASS (no orders).
- Daily loss / capacity / kill-switch unit suite: PASS (53 selected tests).
- Multi-account eligibility / dry-run / registry tests: PASS (23 selected).
- Dry-run dispatch module never calls OMS/`order_send`.
- Safety flags remain: `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`, `FORCE_FIRST_TRADE=false`, `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`.
- Weltrade Program Files LIVE terminal protected (pid observed alive).

## Global execution decision (Phase 4)

**Not enabled.** Owner authorization for enablement is present, but the production gate requires genuine MT5 `trade_allowed=true` for all eight brokers. Enabling submit while three brokers lack trading permission would bypass the required gate.

## Distilled summary

1. **Runtime MT5 connected (8/8):** weltrade, xm, exness, hfm, justmarkets, ic-markets, pepperstone, fp-markets  
2. **Confirmed trading permission (5/8):** weltrade, xm, ic-markets, pepperstone, fp-markets  
3. **Risk / kill-switch:** PASS; global submit remains OFF  
4. **Global execution enabled:** NO  
5. **Production SHA / health:** `1e75cdf3` / health `ok`  
6. **Real orders during acceptance:** none  
