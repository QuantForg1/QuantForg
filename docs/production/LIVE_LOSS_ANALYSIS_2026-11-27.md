# Live loss analysis (journal 2026-10-26 to 2026-11-27)

Source: `live_trade_journal`, 249 closed trades with a stop loss (2 rows had no SL and are excluded from geometry stats).

| Metric | Value |
| --- | --- |
| Net PnL | -131.74 (all rows; gross win 256.09, gross loss 387.83, PF ~0.66) |
| Win rate | ~41% |
| Median stop / target | ~2.5 / ~2.6 price units, median hold ~2.5 min |
| Average spread paid | 0.41 (about 16% of the stop distance) |

## Findings
1. **Before 2026-11-16** (167 trades): TP/SL ratio 0.97, win 45%, avg R -0.18. With ratio ~1 and spread ~0.4 the break-even win rate is ~57%, so a 45% win rate loses by construction.
2. **From 2026-11-16** (82 trades, min net R:R 1.5 enforced): TP/SL 1.99, win 33%, avg R -0.20. Break-even win rate at this geometry is ~39%; 33% on 82 trades is below it but within sampling noise (about +/-5 points). No profitable subset was found by hour, side or stop size.
3. The stop is 1.0 x ATR(M1) (the documented noise boundary), so many stops are hit by noise; the spread is a large share of every trade.
4. 43 of 82 trades since 11-16 were opened outside 07:00-17:00 UTC: the live gate already runs 24/5 (`classify_session_utc` named sessions, `OWNER_SESSION_*` 00:00-23:59 Mon-Fri). The "07:00-17:00" text in `trading_runtime_config.document.session_utc` and several UI labels was stale documentation, not the enforced rule.
5. Increasing the number of trades cannot reduce losses while expectancy per trade is negative; every extra trade pays the spread.

## Changes made (no SL/TP/sizing/threshold change)
- UI/ticket gate labels aligned to the real 24/5 rule (manual ticket no longer blocks 17:00-07:00 UTC).

## Recommended evidence-based experiment (not applied)
Test `stop_atr_multiplier` 1.5 (allowed value) in shadow/paper for at least 100 trades; apply live only if net expectancy per trade is positive after spread. Do not raise trade frequency or lot size before that.
