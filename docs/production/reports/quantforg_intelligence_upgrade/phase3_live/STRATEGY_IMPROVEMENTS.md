# Strategy improvements (LIVE)

All five profiles remain LIVE-evaluable. Phase 3 does **not** disable any strategy.

## Per strategy

| Strategy | Change | Evidence |
|---|---|---|
| `smc_scalping` | Soft regime boost in `weak_trend` / usable in range; can win when TC demoted on LTF disagreement | TC monoculture + SMC 0 accepts historically |
| `trend_continuation` | LTF/HTF disagreement gate; NY MTF≥70 for trendish; regime demotion in range/compression (already forbid) | 2 hard-attributed losers; mixed LTF narrative |
| `breakout_scalping` | Soft boost in `breakout`/`expansion` so equal-quality TC does not auto-supersede | 0 historical accepts despite eval |
| `range_mean_reversion` | Soft boost in range/compression; remain `require_regimes` strict | Correct 0 eligible on trend day |
| `momentum_scalping` | Same LTF/NY trendish gates as TC; soft boost in expansion | Minority accepts historically |

## Opportunity detection (266 scans / 0 eligible)

Funnel showed base/sniper WAIT and Risk blocks — not a SOE monoculture bug in that quiet window. Phase 3 does **not** manufacture signals or lower Q70/RR floors. Diversification applies when multiple strategies **pass** filters.

## Unchanged floors

Registry hard filters (`min_alignment`, `min_momentum`, `require_regimes`, ATR bands) unchanged. Owner Risk/OMS unchanged.
