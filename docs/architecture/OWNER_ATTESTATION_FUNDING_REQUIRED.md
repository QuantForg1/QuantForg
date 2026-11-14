# Owner attestation — LIVE accounts with funding required

## Scope

Applies when a LIVE MT5 account:

1. Authenticates to the correct login + server
2. Reports `trade_mode=2` (REAL)
3. Remains `trade_allowed=false` because the broker requires a deposit / trading activation

Owner attestation records **account identity verification** without enabling LIVE order routing.

## Recorded fields

| Field | UI / primary | Underlying (permission) |
|---|---|---|
| `connection_status` | `live_verified` | same display code |
| `verification_status` | `VERIFIED_LIVE` | — |
| `display_label` | `Verified` | — |
| `verification_method` | (audit) | `OWNER_ATTESTATION` |
| `trading_readiness` | not primary label | `FUNDING_REQUIRED` |
| `trade_allowed` | — | `false` |
| `connectable` | — | `false` (order routing) |
| `trading_enabled` | — | `false` |
| `account_verified` | — | `true` |

Primary Broker Accounts / Admin labels are **Verified** / **VERIFIED_LIVE**.
Do **not** surface `OWNER_VERIFIED_LIVE` or `FUNDING_REQUIRED` as the primary verification badge.
Do **not** set `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=true` or submit orders until funded MT5 verify returns `trade_allowed=true`.

## Current owner-attested accounts (2026-11-14)

| Broker | Login (masked) | Server | Portal evidence |
|---|---|---|---|
| Exness | `***6277` | `Exness-MT5Real10` | Personal Area Real MT5 Standard, balance 0.00 USD |
| HFM | `***2172` | `HFMarketsGlobal-Live20` | Owner attestation (MT5 auth login/server match) |
| JustMarkets | `***0106` | `JustMarkets-Live7` | My accounts Real MT5 Standard, “Activate trading” / Deposit |

## After deposit

Re-run portable verify:

```powershell
.\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env live
```

Promote to trade-ready `live_verified` / `connectable=true` **only** when
`ok=true`, `trade_mode=2`, and `trade_allowed=true`.
