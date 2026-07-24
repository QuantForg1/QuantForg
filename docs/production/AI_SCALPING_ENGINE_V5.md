# Institutional AI Scalping Engine v5

Quality-first upgrade of the live ITE scalping path. **Does not raise risk.** Does not bypass OMS, Risk, or broker safety.

## Timeframes

| Role | TF |
|------|-----|
| Direction | H1 |
| Structure | M15 |
| Entry | M5 |
| Precision | M1 |

## BUY and SELL

Direction from market structure, BOS, CHOCH, liquidity sweeps, order blocks, FVGs, momentum, volume, and session — **never BUY-only**. Highest probability side wins; ties reject.

## Quality gates (all required)

- Strong structure
- High liquidity
- Momentum confirmation
- Tight spread
- Valid volatility
- Session quality
- Adaptive confidence / quality floors
- Minimum expected RR

## Management

- Typical hold **1–10 minutes** (extend only if confidence high)
- Partial profits, break-even, ATR trail
- Momentum-fade exit (do not wait for full SL)
- Dynamic SL behind structure; TP toward liquidity / structure / ATR
- Risk % configurable, **capped ≤ 0.75%**, default **0.50%**
- No martingale / grid

## Universe

XAUUSD, EURUSD, GBPUSD, USDJPY, NAS100, US30, BTCUSD — trade only the best opportunity (Alpha multi-symbol when enabled).

## API / UI

- `GET /ite/reliability/ai-scalping`
- Desk: `/ai-scalping`

## Tests

`tests/unit/test_ai_scalping_v5.py`, `tests/unit/test_ai_scalping_mode.py`
