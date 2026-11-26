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
