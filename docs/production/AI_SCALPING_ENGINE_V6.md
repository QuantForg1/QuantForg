# Institutional AI Scalping Engine v6 — Execution Optimization

Quality-preserving upgrade of the live ITE scalping path. **Does not raise risk.**
Does not replace the existing AI strategy (`decide_scalping_direction` /
`score_scalping_setup`). Does not bypass OMS, Risk, or broker safety.

## Scope

Optimize **execution quality** only:

- Entry confluence adds EMA 20/50/200, RSI, and candle PA (rejection / engulfing)
  on top of existing BOS / CHoCH / liquidity sweep / FVG
- Exits: fixed-R TP preference, ATR TP, partial TP, break-even, ATR / structure /
  liquidity trailing, time stop, **absolute max hold** for scalps
- Session allow-list remains configurable (London / NY / overlap preferred)
- News filter configurable; existing trades still managed by PME / risk
- Durable decision-hash dedupe across process restart (no duplicate OMS submits)
- Richer execution / learning journal fields (entry/exit reason, spread, slippage,
  latency, indicators, rejection)

## Safety locks (unchanged)

- Risk per trade capped ≤ 0.75% (default 0.50%)
- No martingale / grid / unlimited averaging
- Never BUY-only
- Adaptive quality / confidence floors **not loosened**
- Transient OMS retries only (Phase G still forbids blind `order_send` retry)

## Tests

`tests/unit/test_ai_scalping_v6_execution.py`, `tests/unit/test_ai_scalping_v5.py`,
`tests/unit/test_ai_scalping_mode.py`
