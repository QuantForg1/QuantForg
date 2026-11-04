# SOE selection improvements

**Version:** `soe-v1.5.0`  
**Module:** `strategies/soe_intelligence.py` + `orchestrator.py`

## Selection stack (order)

1. Evidence gate (RR, spread, freshness, MTF floor, false-breakout, chase/stale, BUY exhaustion)
2. Passed strategy filters
3. Influence veto (deteriorating stats → weight 0)
4. Regime conflict pairs
5. **NEW:** LTF/session demotion of trendish misfits (TC / momentum)
6. Direction conflict → NO_TRADE
7. Rank = `(quality + live_boost + regime_suitability) * influence + confluence_bonus`
8. Solo / confluent bars (NY raises solo bars)
9. Advisory disagreement bars

## Anti-monoculture

- No hardcoded preferred strategy.
- Regime suitability is a **soft additive**, not a hard lock.
- Equal quality in `breakout` regime: breakout_scalping outranks trend_continuation (unit-tested).
- Weak trend: SMC suitability > TC.

## Influence

Still driven by broker-confirmed StrategyStatsBook health — never by raw signal count.
