# Quant AI Decision Engine V4.0

## Mission

Decide **SHOULD WE TRADE OR WAIT?** — bias strongly to **WAIT**.

Not a blind trading robot. Not a profit guarantee engine.

Optimize for capital preservation, risk-adjusted discipline, controlled drawdown.

## Security

- Never `order_send`
- Never bypass / flip `EXECUTION_ENABLED`
- Default **paper** mode
- Live path never auto-forwards to OMS/EE
- No mock market data

## Architecture

```
/decision-engine
  → /api/v1/decision-engine/dashboard|evaluate|paper/*|reports
  → DecisionEngineService
      ├─ MT5 OHLC (M5/M15/H1/H4/D1)
      ├─ analyze_symbol_structure (domain import from Quant AI — untouched)
      ├─ MarketContext + news calendar
      ├─ Portfolio snapshot (read)
      ├─ scoring / mtf / risk_limits / explanation
      └─ in-memory paper tracker (no schema)
```

## Decision contract

| Field | Meaning |
|-------|---------|
| `decision` | `WAIT` (default) or `TRADE_IDEA` |
| `trade_score` | 0–100 |
| `confidence_pct` | must clear threshold with score |
| `recommended_sl/tp` | advisory only |
| `explanation` | why / may fail / invalidate / improve |

## Locked surfaces

Gateway · Broker Workspace · Terminal · OMS · Execution Engine · TradingSessionProvider · Quant AI · Quant Studio · Auth · existing APIs · DB schema — **untouched**.
