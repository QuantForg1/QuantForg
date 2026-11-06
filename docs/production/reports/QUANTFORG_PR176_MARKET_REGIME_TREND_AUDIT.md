# PR #176 — Market regime and higher-timeframe trend audit

Baseline: `11d5dea7` (PR #175 report). Instrument: XAUUSD. The quality total of 47 is unchanged. This audit asks whether the trend component of 0 is a faithful reading of H1, M15, M5, and M1.

## 1. Executive summary

Trend 0 is the MTF alignment score, not a missing input and not the opportunity score. On the scalping stack, H1 and M15 were both range, so the directional lock has no side and the score is 0. The log phrase `M5=up(timing)` is the execution-slot label. In scalping that slot is M1. The clock M5 trend in that same sentence is the value logged as `M15=range`. M1 being up does not create a higher-timeframe trend. No regime formula was changed.

## 2. Code path for the RANGE result

Live analysis uses `trading_mode=scalping` with timeframes H1, M15, M5, M1 (`ite_cycle_analysis_config`).

1. `MarketStructureEngine.analyze` loads candles through `closed_analysis_bars`, detects fractal swings (`SwingDetector`, left 2, right 2), classifies trend (`TrendClassifier`, last 6 roles), then emits BOS/CHoCH only when that trend is up or down.
2. `TrendEngine.analyze` reads each timeframe's `trend.direction`.
3. It calls `evaluate_mtf_v2` with role slots, not clock names:
   - `h4` = H1 (`macro_bias_tf`)
   - `h1` = M15 (`primary_structure_tf`)
   - `m15` = M5 (`entry_confirmation_tf`)
   - `m5` = M1 (`execution_management_tf`)
4. `overlay_m15_semantics_on_structure` runs first. With no directional H1 bias it returns `UNCHANGED` and does not rewrite M15.
5. `TradeQualityEvaluator._trend` copies `alignment_score`. It raises the score to at least 75 only when `aligned` is true. Here the score is 0 and `aligned` is false, so the quality trend component is 0 of weight 20.

The 00:34 UTC detail was:

`MTF v2 ranging H1+M15 lock (H4=range context): H1=range M15=range M5=up(timing) score=0 not aligned [scalping]`

Decoded onto the clock:

| Role label in the sentence | Clock timeframe | Direction |
| --- | --- | --- |
| H4 | H1 | range |
| H1 | M15 | range |
| M15 | M5 | range |
| M5 | M1 | up |

`frames` on the trend snapshot already stored those clock names. The sentence did not. The quality log now appends `clock H1=... M15=... M5=... M1=...` after the role sentence. The numeric score is the same.

## 3. H1, M15, and M5 evidence

From that decoded sentence:

- H1 structure trend is range. That selects the ranging policy. H1 is context and does not veto a later M15 lock.
- M15 structure trend is range. The lock needs M15 to be up or down. It is not, so the bias is `UNKNOWN` and both lock contributions are 0.
- M5 structure trend is range. It is not the bullish print.
- M1 structure trend is up. The timing bonus is 10 only when a directional bias already exists and M1 matches it. There is no bias, so M1 adds 0.

M15 semantics agreed: `UNCHANGED — No directional structural bias — M15 left unchanged`.

The separate LTF direction engine can still print BUY 24 versus SELL 16 from recent M1/M5 breaks. That engine is not this trend score.

## 4. Formulas

Trend direction, last 6 non-unknown swing roles:

- Up when bullish roles outnumber bearish roles and there are at least two bullish roles.
- Down by the same rule on the bearish side.
- Unknown when no classified roles exist.
- Range otherwise, including a tie.

Swings are fractal highs and lows. A bar is a swing high only when its high is strictly above `left` bars before it and `right` bars after it. The default window is 2 and 2, so the newest two closed bars cannot be a swing. BOS and CHoCH compare a later bar's close with the prior swing. A wick through the level does not qualify. Range and unknown trends emit no BOS and no CHoCH.

Ranging alignment, which is the path taken when H1 is range or unknown:

- Bias is M15 when M15 is up or down, otherwise unknown.
- M15 and M5 each contribute 50 only when they equal that bias. A range or unknown bar on those slots contributes a quarter of the weight, and an opposite bar contributes 0. With an unknown bias both are 0.
- M1 can add 10 only after a bias exists.
- Aligned requires the M15 and M5 lock and a score of at least 55. Score 0 is not aligned.

Trending alignment, used only when H1 itself is up or down:

- Weights are H1 40, M15 30, M5 20, M1 10.
- Opposite H1 versus M15 subtracts 25.
- Aligned requires H1, M15, and M5 to be the same direction and the score to be at least 55.

Opportunity `regime_fit` 58 is a third number. `alignment_score < 55` marks the tape range-like, `classify_scalping_regime` returns `range`, and `_regime_fit("range")` is 58. It does not enter the quality total.

## 5. Confirmed behavior versus defects

Intentional:

- H1 range plus M15 range produces trend 0.
- M1 up does not become higher-timeframe confirmation.
- M5 up, tested separately, also does not create a trend while H1 and M15 are range.
- An agreed H1, M15, M5, and M1 up stack scores 100 and aligns. The same stack down scores 100.
- H1 up against M15 down does not align.
- A missing timeframe is unknown and scores 0.
- Closed bars are the structure input. An open bar at `as_of` is excluded.
- BOS requires a close beyond the prior swing.

Defect, diagnostic only:

- The MTF sentence always prints H4, H1, M15, and M5 even when those slots hold H1, M15, M5, and M1. Reading `M5=up` as clock M5 is wrong. The score did not use that misreading. The clock suffix makes the timeframes explicit.

No threshold was moved. Quality remains a separate weighted average. Opportunity still cannot authorize a trade.

## 6. Historical data and tests

No XAUUSD candle archive is in the repository. There is no chronological holdout and no measured false-transition rate.

Deterministic tests in `tests/unit/test_market_regime_trend_audit.py` cover the production role pattern, an M5-up non-trend, bullish agreement, bearish agreement, H1/M15 conflict, missing data, a role tie classified as range, a wick that does not break structure, a close that does, exclusion of the forming bar, and the two-bar swing confirmation lag. Existing MTF v2, M15 semantics, quality explanation, and direction tests also passed: 62 in the focused run.

## 7. False trend and range findings

Not measurable on historical candles. On the audited scan, calling the tape a higher-timeframe trend would have required treating M1 up as H1 or M15 direction. The code does not do that. That is the conservative result, and it matches the inputs.

## 8. Changes

`TrendEngine.analyze` appends the clock timeframe map to its explanation text. Alignment score, aligned flag, bias, quality weights, and the owner floor are unchanged.

## 9. Production decisions

Unchanged by the formula. A deploy of this diagnostic text does not change who passes quality 70. The 00:34 scan would still be trend 0, quality 47, and `OWNER_MIN_TRADE_QUALITY`.

## 10. Remaining risk and next step

The role sentence is still present, so an older log can still be misread unless the clock suffix is there. Future scans should be read from `clock H1=...`. Do not give M1 or M5 a higher-timeframe vote in order to raise quality. If a later owner decision wants M15 range with internal M1 structure to count as trend, that is a behavior change and needs its own approval.

Owner lot, risk, reward-to-risk, position, and execution protections were not modified.
