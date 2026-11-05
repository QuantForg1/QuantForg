# QuantForg — BUY Cascade Prevention

**Baseline:** `97dc8c29` (#170)  
**Change:** unresolved-decline BUY re-entry guard. Owner floors unchanged. No SL/TP retune. No NY ban. No fabricated direction.

## 1. Cause of BUY cascade losses

Same-symbol requalification treats **any** new structure signature as a fresh setup. During a decline each lower break is a new signature, so another BUY is allowed on the same move. Broker book: 34 BUY, −$28.12; 12 pairs of lower-entry losses in a row; NY BUY −$16.86. Average win +$1.53 vs average loss −$2.33 (RR 0.66). Breakeven would need ~60% win rate; observed 43.5%.

## 2. Fix

After a **losing BUY**, further BUYs are rejected with `BUY_CASCADE_UNRESOLVED_DECLINE` while the new entry is at or below that failed entry, unless:

- price **reclaims** the failed entry, or
- M1/M5 prints a **bullish CHOCH/BOS after the close**.

A winning BUY clears the anchor. SELL is never blocked. Missing prices fail open. `DIRECTION_NONE` is untouched. Anchor is process memory (restart fail-open).

## 3–5. Counterfactual (price rule only, no reversal exception)

Same 46 broker closes, chronological. This is the strict price rule; live will allow extra BUYs when a bullish reversal prints, so live blocks are a subset.

| | Baseline | After price rule |
| --- | --- | --- |
| Trades | 46 | 18 |
| Net | −$29.94 | +$0.71 |
| Expectancy | −$0.65 | +$0.04 |
| PF | 0.50 | 1.05 |
| Max DD (path) | −$34.04 | −$5.69 |
| BUY net | −$28.12 | +$2.53 |
| SELL net | −$1.82 | −$1.82 (unchanged) |

Skipped 28 BUYs including **10 winners** (net of skipped −$30.65).

| Window | Before | After |
| --- | --- | --- |
| Before 5 Nov (in-sample) | −$9.61 (n=29) | +$1.65 (n=16) |
| 5 Nov only (holdout) | −$20.33 (n=17) | −$0.94 (n=2) |
| NY BUY | −$16.86 (n=16) | +$3.47 (n=4) |

Holdout is still **negative** and only two trades. **Not** statistical proof of positive expectancy. The dollar reduction on both windows is why the guard is shipped; the +$0.71 full-sample figure is the same book that exposed the cascade and must not be quoted as a forecast.

## 6. New York

NY BUY losses line up with the same lower-entry cascade, not a separate spread or session bug in this sample. No session ban.

## 7. Legitimate BUY still allowed

Unit tests: entry above the failed BUY is allowed; bullish CHOCH after the close is allowed below the anchor; SELL is never blocked; a winning BUY clears the anchor.

## 8. Not changed

TP/SL geometry, RR floor 0.20, preferred 0.50, Q70, lot 0.01, risk 20%, daily stop, concurrent 1. No per-strategy score (historical `strategy_id` still absent). Attribution path from #166 unchanged.

## 9. Remaining uncertainty

Live reversal prints may re-open some of the 10 skipped winners — or re-open losers. Restart forgets the anchor. Next attributed closes are the only honest check.
