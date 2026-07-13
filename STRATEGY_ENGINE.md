# QuantForg Strategy Engine

Deterministic strategy platform — **not** an AI trader, and **not** an autonomous execution system.

## Principles

| Rule | Behavior |
|------|----------|
| No fake market data | Bars come from the request body or live MT5 candles only |
| No fake trades | Engine emits intentions / signals only |
| No autonomous trading | Never calls `order_send`; never flips `EXECUTION_ENABLED` |
| Explainability | Every signal includes `reason`, `indicator`, `threshold`, `market_context` |
| Preserve stack | ICT Strategy Runtime, Risk, Backtest, Walk-Forward, Paper, Execution, MT5, Provider Layer, Intelligence, auth remain unchanged |

## Core interfaces

Located in `app/domain/interfaces/strategy_engine.py`:

- **StrategyPort** — plugin contract (`evaluate` → `StrategyIntention`)
- **Signal** — `EngineSignalAction`: `BUY` \| `SELL` \| `EXIT` \| `HOLD` + confidence + explanations + timestamp
- **Rule** — custom rule tree (`custom_rules` strategy)
- **Risk** — `StrategyRiskPort` / `StrategyRiskLimits` (max risk, max trades, daily loss, exposure, correlation)

Indicators (pure functions): `app/domain/indicators/` — SMA, EMA, RSI, MACD, Bollinger, momentum, highest/lowest.

## Supported strategies

| Key | Name |
|-----|------|
| `trend_following` | Trend Following (EMA slope) |
| `ma_cross` | Moving Average Cross |
| `rsi` | RSI thresholds |
| `macd` | MACD / signal cross |
| `bollinger` | Bollinger mean reversion |
| `breakout` | N-bar high/low breakout |
| `momentum` | Rate-of-change momentum |
| `mean_reversion` | SMA deviation |
| `custom_rules` | Explicit rule tree |

Plugins live in `app/strategies/`. Orchestration: `app/application/services/strategy_engine.py`.

## HTTP API (additive under `/api/v1/strategy`)

Existing ICT runtime is unchanged:

- `POST /strategy/evaluate`
- `GET /strategy/signals`

New Strategy Engine routes:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/strategy/catalog` | List plugins + default params |
| `POST` | `/strategy/engine/validate` | Validate params / rule tree |
| `POST` | `/strategy/engine/run` | Evaluate → signal + risk + explainability |
| `GET` | `/strategy/portfolio` | Allocations + performance pointers |
| `PUT` | `/strategy/portfolio/allocations` | Set strategy / symbol weights |

### Run request (summary)

```json
{
  "strategy_key": "rsi",
  "symbol": "EURUSD",
  "timeframe": "H1",
  "bars": [{ "open": 1.1, "high": 1.11, "low": 1.09, "close": 1.105 }],
  "params": { "period": 14, "oversold": 30, "overbought": 70 },
  "use_mt5_bars": true,
  "limits": {
    "max_risk_pct": 1.0,
    "max_trades": 5,
    "daily_loss_pct": 3.0,
    "max_exposure_pct": 20.0,
    "max_correlation": 0.8
  }
}
```

If `bars` is empty and `use_mt5_bars=true`, the API loads historical candles via the existing MT5 market-data service. If MT5 has no data, the call fails — bars are never invented.

### Signal shape

```json
{
  "action": "BUY",
  "confidence": 0.65,
  "timestamp": "...",
  "reasons": ["RSI at/below oversold"],
  "explanations": [
    {
      "reason": "RSI at/below oversold",
      "indicator": "RSI",
      "threshold": "oversold=30; overbought=70",
      "market_context": "session=london; state=trending",
      "value": "28.40"
    }
  ]
}
```

## Builder

Frontend Strategy Builder (`/strategy`) includes:

1. **ICT Runtime** — existing confluence flags → `/strategy/evaluate`
2. **TA Engine** — catalog, parameters, custom rule tree, validation → `/strategy/engine/*`
3. Explainability panel for the last engine signal

## Risk gates

Before a BUY/SELL intention is surfaced as actionable:

- Max open trades
- Daily loss %
- Exposure %
- Optional correlation vs `max_correlation`
- Soft confidence cap from `max_risk_pct`

Blocked BUY/SELL/EXIT intentions are coerced to **HOLD** with risk reasons attached.

## Portfolio

In-process allocations (strategy weight + optional symbols). Performance is **not** invented — clients are pointed at:

- `GET /paper/performance`
- `GET /backtests`

## Backtest & Walk-Forward

**No duplicated engines.** Strategy Engine documents integration only:

- Backtest: `POST /backtests/run` → existing `BacktestEngine`
- Walk-forward: `POST /walkforward/run` → existing `WalkForwardEngine`

Use the same OHLC / ICT runtime paths already wired into those engines.

## Execution policy

| `EXECUTION_ENABLED` | Path |
|---------------------|------|
| `false` (default) | Paper only — `POST /paper/orders` |
| `true` | Live allowed via existing `POST /execution/submit` (operator-gated) |

The Strategy Engine **never** submits orders itself. Responses always include:

```json
{
  "execution_policy": {
    "live_requires": "EXECUTION_ENABLED=true",
    "default_path": "paper_trading",
    "autonomous_trading": false
  }
}
```

## Custom rules DSL

```json
{
  "rules": [
    {
      "when": { "indicator": "rsi", "op": "<=", "value": 30 },
      "action": "BUY",
      "reason": "Custom RSI oversold rule"
    }
  ],
  "rsi_period": 14,
  "sma_period": 20
}
```

Supported indicators in conditions: `rsi`, `sma`, `close`. Operators: `<=`, `>=`, `<`, `>`, `==`. First matching rule wins; otherwise HOLD with an explicit “no rule matched” explanation.

## Related docs

- `STRATEGY_RUNTIME_REPORT.md` — ICT confluence runtime
- Execution / paper gates — `EXECUTION_ENABLED` in `.env.example`
