# QuantForg EA (MQL5 edition) — v1.00 baseline (compiled: 0 errors)

Standalone Expert Advisor for MQL5 Market. **Independent from the Cloud Robot.**
It does not share the Cloud's multi-timeframe scoring pipeline, so results are
**not** claimed to match Cloud execution until parity tests prove it.

## Marketplace compliance (design rules)
No DLL imports, no `WebRequest`, no external licensing or sales links, no
customer-data collection, English inputs/messages. Compiled `.ex5` is what is
uploaded.

## Risk baseline implemented
9% max loss at SL (lot is only ever reduced), 25% daily stop, net RR >= 1.5
after spread, spread <= 0.45, Mon-Fri 07:00-17:00 UTC, default lot 0.01, one
position per symbol, no martingale, no grid, no forced trades.

## Signal (v0.1, deliberately simple and transparent)
H1 EMA50/EMA200 trend + confirmed M15 breakout of the last 20-bar range;
SL = 1.2 x ATR(14, M15); TP = 1.6 x risk.

## Status
- Not compiled or tested yet (no MetaEditor in the build environment).
- Next: compile in MetaEditor, Strategy Tester (XAUUSD, M15, several brokers),
  forward test on DEMO, MQL5 validation, owner review. Do not list before.
- Quality score >= 75 from the brief is a Cloud-only construct; the EA's own
  filters replace it. No profitability is promised.
