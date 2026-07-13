# Broker Compatibility Report — Ecosystem v1.1

Priority MT5 retail brands for QuantForg, validated through the **existing live MetaTrader 5 adapter**. No brand-specific sockets. No simulated market data.

**Preserves:** Broker Connectivity Framework, Strategy Engine, Execution Intelligence, Portfolio Intelligence, MT5 integration, APIs, auth, security, DB schema, `EXECUTION_ENABLED`.

## Priority brokers

| Broker | Slug | Platform | Website |
|--------|------|----------|---------|
| Weltrade | `weltrade` | MT5 | https://www.weltrade.com |
| XM | `xm` | MT5 | https://www.xm.com |
| Exness | `exness` | MT5 | https://www.exness.com |
| IC Markets | `ic-markets` | MT5 | https://www.icmarkets.com |
| Pepperstone | `pepperstone` | MT5 | https://pepperstone.com |

## Compatibility matrix (declared + live)

Checks: login · account sync · balances · equity · positions · pending orders · history · symbols · quotes · candles · paper trading · execution checks

| Status | Meaning |
|--------|---------|
| `compatible` | Live MT5 probe returned `ok` for the **matched** brand session |
| `pending_session` | Operator must connect that brand’s MT5 account — **not** a fake pass |
| `unavailable` | Probe could not run (disconnected / missing DI) |
| `documented` | Path exists as documentation (e.g. execution gate) without inventing fills |
| `error` | Live probe raised an error |

Without an operator MT5 login, all five brands report `pending_session` for account/market checks. That is correct — QuantForg does not invent broker connectivity.

When a session is connected, the server string is matched to a brand pattern (hints only). **Only the matched brand** receives live probe results; others stay `pending_session`.

## Capability profiles

Each brand declares MT5 retail capabilities (order types, margin, leverage, netting/hedging, market data, history). Streaming push is `false` (same as platform MT5 adapter — no invented WS).

Source: `app/domain/broker_connectivity/mt5_ecosystem.py`

## Onboarding guides

Per-brand steps via `GET /broker-connectivity/onboarding/{slug}` and UI `/broker-compatibility`:

1. Open / verify account at broker website  
2. Install MetaTrader 5  
3. Use **exact** server from portal/email (hints are search aids only)  
4. Connect in QuantForg `/mt5`  
5. Validate on `/broker-compatibility`  
6. Paper (`/paper`) then gated execution (`/execution/check`)

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/broker-connectivity/ecosystem` | v1.1 brand profiles |
| GET | `/broker-connectivity/compatibility` | Live suite + matrix |
| GET | `/broker-connectivity/compatibility/dashboard` | Dashboard payload |
| GET | `/broker-connectivity/onboarding/{slug}` | Onboarding guide |

Also included in `GET /broker-connectivity/dashboard`.

## UI

`/broker-compatibility` — matrix, onboarding, per-check detail, operator actions.

## Remaining operator actions

1. Obtain demo/live credentials from each priority broker portal.  
2. Connect via `/mt5` with the **exact** assigned server string.  
3. Refresh `/broker-compatibility` and confirm the matched brand cells turn `compatible`.  
4. Repeat per brand (one live MT5 session at a time).  
5. Keep `EXECUTION_ENABLED` off until intentional live trading; use paper + `/execution/check` first.  
6. Do not treat documented profiles or server hints as live quotes.

## Related

- `BROKER_CONNECTIVITY.md`  
- Live MT5: `/mt5/*`  
- Execution: `/execution/check`, `/execution/submit`  
- Paper: `/paper/*`
