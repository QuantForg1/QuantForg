# MT5 server discovery — eight brokers

## Mechanism

QuantForg does **not** call a public MetaQuotes “list all servers” API (none is
available for arbitrary brokers). Discovery uses:

1. **CONFIRMED** — authenticated Windows portable / gateway verify (`trade_allowed`
   from `account_info`, server string exactly as MT5 returned).
2. **DOCUMENTED / CANDIDATE** — exact names observed in the native MT5
   *Open an Account → Server* dropdown (owner screenshots 2026-11-13) or broker
   portal, stored as `server_hints` on each ecosystem profile.
3. **Manual paste** — customer may enter the exact portal/terminal server name.

Candidates are **never** promoted to CONFIRMED by naming pattern alone.

## Coverage (2026-11-14)

| Broker | Confirmed LIVE | Candidate / documented discovery | Limitation |
|---|---|---|---|
| Weltrade | `Weltrade-Real` (+ Demo) | `Weltrade-Demo`, `Weltrade-MT5` | Full native list is short (Real/Demo). |
| XM | `XMGlobal-MT5 20` | `XMGlobal-MT5 2`…`22`, other brand prefixes | Numbered rows from MT5 Open Account; env only confirmed after login. |
| Exness | `Exness-MT5Real10` (auth OK) | Many `Exness-MT5RealN` / `TrialN` from MT5 list | Full MetaQuotes directory not enumerable via API; list is observed subset. |
| HFM | `HFMarketsGlobal-Live20` (auth OK) | Demo/Live entity variants | Same — no complete remote directory API. |
| JustMarkets | `JustMarkets-Live7` (auth OK) | Live/Demo entity variants | Same. |
| IC Markets | `ICMarketsSC-MT5-3` | SC/EU/Demo variants | Same. |
| Pepperstone | `PepperstoneKE-MT5-Live01` | Live/Demo entity variants | Same. |
| FP Markets | `FPMarketsSC-Live` | SC/KE/Demo variants | Same. |

## Refresh

When new genuine servers are observed in MT5 or verified via portable login,
append exact strings to `mt5_ecosystem.py` `server_hints` (candidates) or
`_EVIDENCE_VERIFIED_LIVE` / evidence store (confirmed). Do not invent shard
numbers.
