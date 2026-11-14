# Owner trade enablement — display vs MT5 permission

## Authorization (display)

Product-owner instruction: all eight LIVE brokers may show **Verified** and
**connectable=true** in Broker Accounts Production after authenticated login
evidence (or owner attestation of the correct LIVE login/server).

| Broker | Display | Connectable | MT5 `trade_allowed` |
|---|---|---|---|
| Weltrade | Verified | true | true (gateway) |
| XM | Verified | true | true (portable verify) |
| Exness | Verified | true | **false** until broker activates trading |
| HFM | Verified | true | **false** until broker activates trading |
| JustMarkets | Verified | true | **false** until broker activates trading |
| IC Markets | Verified | true | true (portable verify) |
| Pepperstone | Verified | true | true (portable verify) |
| FP Markets | Verified | true | true (portable verify) |

## Hard rule

Never set `trade_allowed=true` / `trading_enabled=true` in catalogue, evidence,
fixtures, or UI as a substitute for MetaTrader 5 `account_info.trade_allowed`.

`OWNER_TRADE_ENABLEMENT` authorizes **Verified + connectable** display only.
Re-run portable LIVE verify after funding/activation; ingest genuine
`trade_allowed` from MT5 before treating a broker as trading-ready.

## Implementation

- Catalogue: `_OWNER_AUTHORIZED_LIVE_CONNECTABLE` for Verified/connectable.
- Catalogue: `_AUTH_OK_TRADE_NOT_ENABLED` for Exness / HFM / JustMarkets until
  `WINDOWS_MT5_VERIFY` reports `trade_allowed=true`.
- Catalogue: `_GENUINE_MT5_TRADE_ALLOWED` for XM / IC / Pepperstone / FP Markets.
- Frontend static registry may mark all eight `live_verified` / `connectable`
  for customer discovery; runtime permission gates remain separate.

## Safety

- `FORCE_FIRST_TRADE` remains **false**.
- `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` remains **false** (Weltrade Program Files singleton).
- Global `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` stays **false** until all eight
  brokers have genuine MT5 `trade_allowed=true` plus risk/kill-switch gates.
