# MQL5 Market listing text (v1.01)

**Name:** QuantForg Gold Breakout EA
**Symbol / TF:** XAUUSD, attach to M15 chart. Hedging or netting account.

**Description**
Trend-filtered breakout robot for gold. A trade is considered only when the H1 EMA50/EMA200
trend agrees with a confirmed M15 breakout of the last 40 bars, during 07:00-12:00 UTC,
Monday-Friday. Every trade has a stop loss (2.0 x ATR) and take profit (2.5 x risk), one
position at a time, spread filter, lot is reduced so a stop-out never exceeds the risk cap,
and a daily stop. No martingale, no grid, no averaging down.

**Important risk notice**
Trading gold is high risk and you can lose your capital. Past or tested results do not
guarantee future results. This robot wins roughly one trade in three and relies on larger
winners than losers; losing streaks are normal. Test on a demo account first. Results depend
on broker, spread and execution. Recommended: start with the default 0.01 lot.

**Inputs:** lot, max risk %, daily stop %, max spread, session hours, breakout bars, ATR period/multiplier, RR, magic number.
**Do not** add screenshots or numbers that were not produced by your own Strategy Tester run.

## Pricing recommendation (owner decides)
- Launch price: **$79** one-time (MQL5 minimum is $30; typical XAUUSD EAs list $99-$399, but this one has ~1 year of tester evidence and no live track record yet). Raise to $129-$199 after 2-3 months of public demo/live results.
- MQL5 keeps 20% commission; MQL5 licence and activations are handled by MQL5 (no own licensing in the EA).
- Offer a free demo (MQL5 provides a Market demo download) so buyers can test before buying.
- Only publish screenshots from your own Strategy Tester runs. Strategy Tester 2025-12 to 2026-11 (v1.01): PF 2.02, 88 trades, win 44%, equity DD 4.4%, history quality 63%. Also state that the prior 12 months were weak in our research and no result is guaranteed.
- Pending before upload: Strategy Tester on 2024-12 to 2025-11 (stress), then a >=1 month demo forward test.
