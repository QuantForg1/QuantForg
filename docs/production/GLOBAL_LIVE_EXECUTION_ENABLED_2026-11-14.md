# Global LIVE execution enabled — owner order 2026-11-14

## Flags (Production Railway + Windows host `local.env`)

| Flag | Value |
|---|---|
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | **true** |
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | **true** |
| `FORCE_FIRST_TRADE` | **false** |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | **false** |

Emergency kill-switch / disarm paths remain operational. This enablement does
**not** auto-submit a first trade.

## Broker registry (owner-authorized)

| Broker | Verified | Trading permission | `trade_allowed` |
|---|---|---|---|
| Weltrade | YES | YES | true |
| XM | YES | YES | true |
| Exness | YES | YES | true |
| HFM | YES | YES | true |
| JustMarkets | YES | YES | true |
| IC Markets | YES | YES | true |
| Pepperstone | YES | YES | true |
| FP Markets | YES | YES | true |

## Note

Owner explicitly ordered enablement despite prior portable verifies showing
Exness / HFM / JustMarkets MT5 `account_info.trade_allowed=false` (balance 0).
Broker rejects may still occur until those accounts are funded/activated.
