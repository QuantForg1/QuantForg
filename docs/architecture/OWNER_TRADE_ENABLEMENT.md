# Owner trade enablement — eight LIVE brokers

## Authorization

Product-owner instruction (2026-11-14): all eight LIVE brokers are
**Verified**, **connectable=true**, and **trade_allowed / trading_enabled=true**
in Broker Accounts Production.

| Broker | Display | Connectable | Trading enabled |
|---|---|---|---|
| Weltrade | Verified | true | true |
| XM | Verified | true | true |
| Exness | Verified | true | true |
| HFM | Verified | true | true |
| JustMarkets | Verified | true | true |
| IC Markets | Verified | true | true |
| Pepperstone | Verified | true | true |
| FP Markets | Verified | true | true |

## Implementation

- Catalogue ships `_OWNER_AUTHORIZED_LIVE_TRADE` for Exness / HFM / JustMarkets.
- Evidence may record `OWNER_TRADE_ENABLEMENT` while preserving prior auth history.
- Frontend static registry marks all eight `live_verified` / `connectable`.

## Safety

- `FORCE_FIRST_TRADE` remains **false**.
- `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` remains **false** (Weltrade Program Files singleton).
- Global `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` is a separate host/Railway kill-switch
  and is not flipped by catalogue display enablement alone.
