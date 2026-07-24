# Institutional Alpha Engine v5

Extends ITE Auto Trading / AI Scalping with a multi-symbol institutional desk.
Does **not** replace OMS, Risk, Safety, MT5 Gateway, or PME.

## Enable

1. Set Railway / env: `INSTITUTIONAL_ALPHA_ENABLED=true` (lifts gold-only for Alpha)
2. Auto Trading → **Institutional Alpha**, or open `/institutional-alpha` → Enable Alpha

API:

```http
POST /api/v1/ite/ops/auto-trading
{
  "confirmed": true,
  "reason": "enable alpha",
  "trading_mode": "alpha",
  "alpha_engine_enabled": true,
  "max_open_positions": 3,
  "allowed_symbols": ["XAUUSD","EURUSD","GBPUSD","USDJPY","NAS100","US30","BTCUSD"]
}
```

Dashboard: `GET /api/v1/ite/ops/institutional-alpha`

## Behaviour

Every cycle:

1. Scan the configured universe
2. Score Opportunity (confidence, trend, momentum, liquidity, volatility, spread, RR, session)
3. Rank highest first
4. Block correlated books (e.g. EURUSD+GBPUSD, NAS100+US30)
5. Allocate risk by quality band + smart recovery
6. Execute only the top eligible setup through the **existing** OMS path

## AI position management

PME evaluates open trades with optional AI confidence hints:

- Large confidence drop → exit (configured)
- Moderate drop → reduce size
- High confidence → wider ATR trail (let profits run)
- Weak confidence → tighter trail

## Smart recovery

After a loss: temporary risk multiplier + higher min opportunity score.
Never Martingale, Grid, or averaging down.

## Safety

All existing protections remain: margin, market open, spread ceiling, daily loss,
drawdown, emergency stop, broker distance, duplicate guards, symbol validation.
