# Owner trade enablement — eight LIVE brokers (2026-11-14)

## Authorization

Product-owner order (2026-11-14): enable **Global LIVE Execution**, set
`MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true`, and mark all eight LIVE brokers
**Verified** with **Trading Permission = YES** / `trade_allowed=true` for
Broker Accounts, registry, and Admin.

| Broker | Display | Connectable | Trading permission |
|---|---|---|---|
| Weltrade | Verified | true | YES |
| XM | Verified | true | YES |
| Exness | Verified | true | YES |
| HFM | Verified | true | YES |
| JustMarkets | Verified | true | YES |
| IC Markets | Verified | true | YES |
| Pepperstone | Verified | true | YES |
| FP Markets | Verified | true | YES |

## Safety (still enforced)

- `FORCE_FIRST_TRADE=false` (no automatic first trade)
- `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false` (Weltrade Program Files singleton)
- Emergency / kill-switch paths remain operational
- `MULTI_ACCOUNT_DISPATCH_ENABLED=true` is required together with live submit
- Setting the submit flag does **not** by itself place orders

## Note

Prior portable verifies showed Exness / HFM / JustMarkets MT5
`account_info.trade_allowed=false` with zero balance. Owner explicitly
overrode the fleet gate for Production enablement. Broker-side rejects may
still occur until those accounts are funded/activated at the broker.
