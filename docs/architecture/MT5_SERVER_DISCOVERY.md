# MT5 server discovery — eight brokers

## Mechanism

QuantForg does **not** call a public MetaQuotes “list all servers” API (none is
available for arbitrary brokers). Discovery uses:

1. **CONFIRMED** (internal) — authenticated Windows portable / gateway verify
   (`trade_allowed` from `account_info`, server string exactly as MT5 returned).
2. **Documented discovery** — exact names observed in the native MT5
   *Open an Account → Server* dropdown (owner screenshots) or broker portal,
   stored as `server_hints` on each ecosystem profile.
3. **Manual paste** — customer may enter the exact portal/terminal server name.

## Customer-facing selection (Broker Page 2.0)

- Every genuinely discovered server is a normal selectable option.
- **No** Confirmed / Candidate / LIVE / DEMO badges in the dropdown.
- Search + optional paste; QuantForg authenticates with the **exact** selected
  or pasted name (never silently substituted).
- Account environment is still resolved **internally** from the server name
  heuristic and finally from MT5 account metadata after authentication.

## Coverage

| Broker | Genuine discovery source | Notes |
|---|---|---|
| Weltrade | MT5 Open Account: `Weltrade-Real`, `Weltrade-Demo` | Short native list. |
| XM | MT5 Open Account numbered `XMGlobal-MT5 N` + verified LIVE | Env confirmed after login. |
| Exness | MT5 Open Account `Exness-MT5RealN` / `TrialN` + verified | Observed subset; not a full MetaQuotes directory dump. |
| HFM | Verified LIVE + documented entity variants | Same API limitation. |
| JustMarkets | Verified LIVE + documented variants | Same. |
| IC Markets | Verified LIVE + documented variants | Same. |
| Pepperstone | Verified LIVE + documented variants | Same. |
| FP Markets | Verified LIVE + documented variants | Same. |

## Refresh

Append exact newly observed strings to `mt5_ecosystem.py` `server_hints` or
evidence store. Never invent shard numbers.
