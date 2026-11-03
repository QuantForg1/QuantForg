# Strategy loss root-cause snapshot — 2026-11-03

**Source:** Live MT5 gateway `GET /history/deals?days=30` (magic `260720` QuantForg deals).  
**Method:** Position-id grouping heuristic for closed-trade estimates.  
**Not claimed:** Guaranteed future edge. Strategy pack IDs were **not** present in MT5 comments.

## Observed (estimated)

| Metric | Value |
|--------|-------|
| Estimated closed QF positions | 29 |
| Wins / Losses | 14 / 15 |
| Net (profit field; commission often 0 in feed) | **-9.61** |
| Avg win / Avg loss | **+1.45 / -2.00** |

## Key finding

Comment samples are dominated by **`m1:mom-buy-*`** (M1 micro momentum buys), not SOE five-pack ids (`smc_scalping`, etc.).  
`STRATEGY_ID_IN_COMMENTS = false`.

Implication: recent net drag is consistent with **M1 micro path** fills and **asymmetric R** (losses larger than wins), not with proven five-pack SOE outcomes.

## Remediation shipped in SOE v1.1

- Fill metadata now stores `strategy_id` for closed-loop `StrategyStatsBook` (comment format unchanged).
- Advisory collaboration + cost gate + disagreement bar reduce weak entries on the primary scalping pack.
- M1 remains ops-gated via unified decision; do not silently treat M1 comments as five-pack performance.

## Owner guidance

1. Keep LIVE objective under existing gates.
2. Review whether `m1_live_submit` should stay enabled while avg loss > avg win.
3. After new fills, verify ops monitor shows strategy_id attribution on closes.
4. Prefer NO_TRADE / SHADOW for M1 until matched expectancy recovers — without claiming permanent SHADOW for the whole desk.
