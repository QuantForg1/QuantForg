# AI Scalping Engine v4

Extends the Institutional Trading Engine (ITE) Auto Trading path with a dedicated
**Scalping Mode**. Does not replace OMS, MT5 Gateway, Risk Engine, or Position Manager.

## Enable

On **Auto Trading** dashboard → Operator controls:

1. Click **AI Scalping**
2. Optionally enable **Compounding** (growth-only; never martingale/grid)
3. Confirm **Max open** defaults to **3** when Scalping is selected

API:

```http
POST /api/v1/ite/ops/auto-trading
{
  "confirmed": true,
  "reason": "enable scalping",
  "trading_mode": "scalping",
  "compounding_enabled": false,
  "max_open_positions": 3
}
```

## Timeframes (Scalping)

| Role | TF |
|------|----|
| Direction filter | H1 |
| Structure | M15 |
| Entry confirmation | M5 |
| Execution timing | M1 |

H4 is **never** required in Scalping Mode.

## Adaptive thresholds

Resolved from live ATR% (never fixed at evaluation):

| Band | Quality | Confidence |
|------|---------|------------|
| High vol | ≥70 | ≥72 |
| Normal | ≥78 | ≥78 |
| Low vol | ≥85 | ≥85 |

Knobs live in `AiScalpingConfig` (`app/domain/institutional_trading/ai_scalping/`).

## Safety (always on)

Margin · broker · market open · emergency stop · max drawdown · daily loss ·
spread ceiling · duplicate entry guard · symbol · broker distance · risk limits.

Force First Trade (if armed) still only waives Quality / Confluence / MTF — never the above.

## Smart management

PME policies for scalping use faster BE / partial / ATR trail knobs from `AiScalpingConfig`.

## Self-learning

Closed-trade outcomes can be recorded in `ai_scalping_learning.json` and feed a
historical similarity prior into the AI score.

## Execute Now

`POST /api/v1/ite/ops/auto-trading/execute-now` runs one full Auto Trading cycle
(same pipeline as the scheduler) and returns the exact OMS/broker result.
