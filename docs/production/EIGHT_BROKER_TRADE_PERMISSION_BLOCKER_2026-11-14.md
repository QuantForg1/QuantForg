# Eight-broker trade permission — owner enablement blocked (2026-11-14)

**Owner request:** genuine `trade_allowed=true` for all eight LIVE brokers, then enable global LIVE submit.  
**Production SHA at check:** `5338a2d0`  
**Orders submitted:** **0**  
**Global LIVE submit:** remains **`MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`**  
**`FORCE_FIRST_TRADE`:** remains **`false`**

## Runtime re-verify (portable `demo-a`, ~14:55 local)

| Broker | Server | Connected | Balance | `trade_mode` | `trade_allowed` | Result |
|---|---|---|---|---|---|---|
| Exness | `Exness-MT5Real10` | YES (auth) | **0.00** | 2 | **false** | `authenticated_trading_not_enabled` |
| HFM | `HFMarketsGlobal-Live20` | YES (auth) | **0.00** | 2 | **false** | `authenticated_trading_not_enabled` |
| JustMarkets | `JustMarkets-Live7` | YES (auth) | **0.00** | 2 | **false** | `authenticated_trading_not_enabled` |

Root cause is **broker-side**: MT5 `account_info.trade_allowed` is false with zero balance. This is not an adapter defect, wrong server, or investor-password mis-read (session authenticates on the correct LIVE login/server).

QuantForg **cannot** set `trade_allowed=true` in application code, catalogue, evidence, or fixtures as a substitute for MetaTrader 5 account permission.

## Gate decision

| Gate | Status |
|---|---|
| 8/8 MT5 connected | Conditional (5 previously PASS + 3 auth-OK) |
| 8/8 genuine `trade_allowed=true` | **FAIL (5/8)** |
| Enable `MULTI_ACCOUNT_LIVE_SUBMIT` | **NOT ENABLED** |
| Deploy permission override | **NOT DONE** |

## Owner action required

1. Fund / activate trading on Exness, HFM, and JustMarkets LIVE accounts in each broker portal.  
2. Confirm in native MT5 that Algo Trading / trade is allowed and balance &gt; 0 (or broker explicitly enables trading on zero-balance accounts).  
3. Re-run:  
   `.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker &lt;slug&gt; -Slot demo-a -Env live`  
   until each returns `trade_allowed=true`.  
4. Then authorize enabling `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true` on the Windows host / Railway (still keep `FORCE_FIRST_TRADE=false`).

## Previously confirmed PASS (portable LIVE evidence)

Weltrade, XM, IC Markets, Pepperstone, FP Markets — `trade_allowed=true` from Windows MT5 verify (retained; not re-fabricated).
