# Phase 3 — LIVE intelligence upgrade summary

**Owner decision:** No Shadow Mode. Validated improvements implemented for LIVE.  
**SOE version:** `soe-v1.4.0` → `soe-v1.5.0`  
**Baseline (Phase 2):** 13 broker closes, net **-$8.48**, WR 46%, PF ~0.59, expectancy ~-$0.65/trade, equity ~$15.52.

## What shipped

| Area | Change | Risk policy |
|---|---|---|
| SOE selection | Regime-suitability ranking (soft); no hardcoded `trend_continuation` preference | Unchanged |
| MTF / LTF | Trendish strategies demoted/blocked on HTF/LTF disagreement when LTF artefacts present | Unchanged |
| NY session | Raised solo quality/confidence bars; trendish need MTF≥70 in NY | Session not disabled |
| Entry quality | Chase/stale sniper + BUY exhaustion evidence vetoes | Unchanged |
| Attribution | Strategy hints captured before binding clear on broker close | Analytics only |
| Owner risk | RR 0.20 / Q70 / lot 0.01 / concurrent 1 / 20% risk / 48% daily / M1 LIVE OFF | **Preserved** |

## Validation snapshot

- Unit: `test_soe_intelligence_phase3.py` + orchestration/collaboration suites — **pass**
- Offline counterfactual on 2 hard-attributed TC NY losers with mixed-LTF factors: **both blocked**; avoided **$3.55** in that counterfactual (not a profit promise)
- OWNER_SL_RISK: at ~$15.52 equity, 20% ceiling ≈ **$3.10**; keep rejection when 0.01 lot SL distance exceeds ceiling

## Explicit non-promises

- Does not guarantee future profitability or higher trade count.
- Does not invent fills or lower owner floors to force trades.
- Zero eligible in quiet windows can remain correct (prefer no trade).

## Deliverables

See sibling files in this directory for strategy, SOE, MTF, NY, loss, backtest, deployment, and limitations detail.
