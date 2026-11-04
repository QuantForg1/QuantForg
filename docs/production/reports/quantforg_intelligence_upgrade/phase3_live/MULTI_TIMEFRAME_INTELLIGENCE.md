# Multi-timeframe intelligence (LIVE)

## Mechanism

When live scoring attaches LTF artefacts (`m5_entry`, `m5_bos`, `m15_structure`, LTF buy/sell scores):

| Check | Applies to | Action |
|---|---|---|
| Regime range/compression | `trend_continuation`, `momentum_scalping` | Demote candidate |
| `m5_entry=0` and MTF&lt;75 | trendish | Demote |
| Opposing LTF lean vs direction | trendish | Demote |
| Weak M5/M15 structure and MTF&lt;80 | trendish | Demote |
| Global MTF&lt;55 | all (existing) | Prefer NO_TRADE |

Absent LTF keys (partial fixtures) do **not** invent disagreement — preserves test/legacy scores.

## Timeframes

Uses already-supported M5/M15 structure factors from direction/scoring. M1 LIVE submissions remain **OFF**.

## Goal

Improve entry decisions on continuation entries into mixed LTF tape **without** blocking every opportunity (SMC/breakout/range can still select when they pass).
