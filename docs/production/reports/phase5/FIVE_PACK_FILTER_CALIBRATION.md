# Phase 5 — Five-pack filter calibration (XAUUSD)

**Decision:** No threshold loosening. Owner floors Q≥75 and net RR≥1.50 remain binding.

## Observed production rejects (Phase 4 window)

| Filter | Observed | Strategy-specific? | Verdict |
|---|---|---|---|
| ATR% hard min 0.08 | ATR% ≈ 0.0676 | Shared SCALPING_V1 / vol gate v2 | **Correct reject** — dead-tape evidence floor (`docs/trading/VOLATILITY_GATE_CALIBRATION_REPORT.md`). 0.0676 is below the absolute gold hard min. |
| Owner quality 75 | AI quality ≈ 68 | Shared owner floor | **Correct reject** — owner-approved; not lowered. |
| Net RR 1.50 | No OMS winner | Shared owner floor (Phase-5 locked) | **Correct** — must clear after spread/commission/slippage. |
| Direction / TP room | Balanced scores | Shared | **Correct** — prefer NO_TRADE without edge. |
| ATR band high/normal | breakout only | Yes (`require_atr_band`) | **Correct** — breakout needs non-low band. |
| Regime range/compression | range_mean_reversion only | Yes | **Correct** — strong_trend is out of design regime. |

## Shared vs strategy-specific ATR

- Hard ATR% floor is **intentionally shared** across the five-pack via SCALPING_V1 base gates — these are scalping profiles that require tradeable gold tape.
- Strategy-specific ATR **band** filters (breakout) and **regime** filters (range) sit on top; they do not replace the hard min.
- Lowering the shared hard min to admit 0.0676 would increase noise fills without walk-forward evidence that expectancy improves after costs.

## Evidence standard for future changes

Only adjust a filter when:

1. Matched broker closed outcomes show the filter removes positive expectancy setups, and
2. Out-of-sample / walk-forward checks (with spread + commission + slippage) confirm the change does not degrade net expectancy, and
3. Owner floors Q75 / RR 1.50 stay intact unless the owner changes them.

**Phase-5 action:** keep evaluating; continue NO_TRADE until tape/quality clear floors. No code threshold change.
