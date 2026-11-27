# QuantForg EA (MQL5 edition) — v1.01 (Approved for Sale)

Standalone Expert Advisor for MQL5 Market. **Independent from the Cloud Robot.**
It does not share the Cloud's multi-timeframe scoring pipeline, so results are
**not** claimed to match Cloud execution until parity tests prove it.

## Marketplace compliance (design rules)
No DLL imports, no `WebRequest`, no external licensing or sales links, no
customer-data collection, English inputs/messages. Compiled `.ex5` is what is
uploaded.

## Risk baseline implemented
9% max loss at SL (lot is only ever reduced), 25% daily stop, net RR >= 1.5
after spread, spread <= 0.45, Mon-Fri 07:00-12:00 UTC, default lot 0.01, one
position per symbol, no martingale, no grid, no forced trades.

## Signal (v0.1, deliberately simple and transparent)
H1 EMA50/EMA200 trend + confirmed M15 breakout of the last 40-bar range;
SL = 2.0 x ATR(14, M15); TP = 2.5 x risk.

## Status
- Not compiled or tested yet (no MetaEditor in the build environment).
- Next: compile in MetaEditor, Strategy Tester (XAUUSD, M15, several brokers),
  forward test on DEMO, MQL5 validation, owner review. Do not list before.
- Quality score >= 75 from the brief is a Cloud-only construct; the EA's own
  filters replace it. No profitability is promised.

## v1.01 status (honest)
v1.00 failed the gate (PF 0.93). v1.01 uses the parameter set chosen most often by
rolling walk-forward (9m train / 3m test, 216 variants): OOS PF 1.36, 208 trades,
but win rate ~35% (gate wants >=40%) and gains are concentrated in the last 3
windows of 20-27 trades each. Full-sample PF 1.58 is in-sample, not evidence.
**Do not list on MQL5 Market or run live until: Strategy Tester 1y passes, and a
DEMO forward test of >= 1 month confirms.** Research script: `research/ea_walkforward.py`.

## Release decision
v1.01 is Approved for Sale (owner decision, 2026-11-26). Recorded for the audit trail: the
internal backtest gate is NOT met (win rate ~35% vs 40%; OOS evidence is limited).
The listing therefore makes no profit claims and states the risk plainly
(see `MQL5_LISTING.md`). Improvements ship as new versions (1.02, 1.03 ...).
