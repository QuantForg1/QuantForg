# QuantForg Institutional Trading Engine — Phase 1

**Date:** 2026-07-14  
**Scope:** Institutional Trading Terminal UI (frontend) — no gateway / session bind / API contract changes.

## Architecture

```
MT5 live session (TradingSessionProvider)
        ↓
Institutional Trading Terminal (/workspace + /execution)
├── Left: Market Watch (broker symbols, categories, live tick)
├── Center: Professional chart (lightweight-charts ← mt5Api.candles)
├── Right: Order ticket + account/risk (session + risk/execution APIs)
└── Bottom: Positions · Orders · History · Journal · Logs
```

Chart uses TradingView-class UX via `lightweight-charts` fed **only** by MT5 candles (TradingView Advanced Charts would use TV market data — rejected to honor real-broker-only rule).

## Validation

- `tsc --noEmit`: pass
- `npm run lint`: pass (warnings only if any)
- `npm run build`: pass
- `pytest tests/unit`: pass

## Security

- Passwords / tokens not exposed in terminal UI
- Live `order_send` still gated by `EXECUTION_ENABLED`
- Pre-trade checklist + `/risk/check` + `/execution/check` before submit
