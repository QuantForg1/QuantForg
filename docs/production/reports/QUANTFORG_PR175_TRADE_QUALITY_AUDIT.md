# PR #175 — Trade Quality Engine audit

Baseline: `bc79dbac` (PR #174). Instrument: XAUUSD. Evidence window: Railway deployment `e5f80628`, scans at 2026-11-06T00:09:19Z through 00:10:10Z.

## 1. Executive summary

Trade quality 47 and opportunity 76–77 are different calculations. The execution gate uses the quality integer. It does not use the opportunity score. The published rejection `OWNER_MIN_TRADE_QUALITY: trade quality 47 < 70` is the same integer the evaluator published. No scoring weight was changed.

## 2. Why quality is 47

`TradeQualityEvaluator.evaluate` builds seven component scores and publishes:

`total = round(sum(score * weight) / sum(weight))`

The weights sum to 100:

| Component | Weight | What it reads |
| --- | ---: | --- |
| trend | 20 | `trend.alignment_score`, raised to at least 75 only when `trend.aligned` is true |
| liquidity | 15 | Liquidity v2: 85 with a sweep, 65 with other context, 20 with none |
| order_block | 15 | 0 if the snapshot is missing; otherwise 20, 55, 75, or 85 |
| fair_value_gap | 15 | 0 if missing; 25 if only closed gaps; 70 if one open gap; 85 if two or more |
| market_structure | 15 | Primary-timeframe structure only. Base 30, then swings, BOS, CHOCH, and trend direction |
| session | 10 | UTC session quality |
| spread | 10 | Linear from full score to reject |

`score_ai_scalping` assigns `trade_quality = int(quality.total)`. The owner gate compares that integer with `active_min_trade_quality()`, which is 70 unless a saved policy sets 70–100. The scan text `trade quality 47 < 70` is that comparison. There is no second quality formula in the Risk Engine or OMS.

### Inputs proven from the 00:09 UTC scan

The analysis config log shows `trading_mode=scalping`, timeframes `H1, M15, M5, M1`, primary `M15`, `requires_h4=False`.

The scalping spread band is full score at 0.40 and reject at 1.50. Spread 0.424 therefore scores `int(100 * (1 - (0.424 - 0.40) / 1.10)) = 97`. Weight 10 contributes 970 weighted points, 9.7 of the published total.

2026-11-06 00:09 UTC is a Friday. `classify_session_utc` returns Tokyo. Tokyo has 2 stars and quality 55. Weight 10 contributes 550 weighted points, 5.5 of the published total.

Those two components account for 1,520 of the weighted points. A published total of 47 requires the weighted sum to land in `[4650, 4750)`. The other five components therefore contributed about 3,130 to 3,230 points between them (an average component score near 40 on a combined weight of 80). Their individual scores were not in the scan log. They are not reconstructed here.

## 3. Component status

| Question | Evidence |
| --- | --- |
| Direction confidence | Not a quality component. Direction was BUY, LTF 24 vs 16, edge 8. `ai_confidence` was 53. |
| M1/M5 structure | Used by `decide_scalping_direction`. Quality structure reads the primary snapshot, which is M15 on this config. |
| Momentum | Opportunity momentum was 78. Quality has no momentum factor. The trend factor is alignment, not the LTF momentum flag. |
| Volatility and regime | Opportunity regime fit was 58 and volatility 74. Neither is a quality component. |
| Multi-timeframe alignment | Quality trend uses MTF v2 alignment on the scalping stack. The slots named H4/H1/M15/M5 in `evaluate_mtf_v2` receive H1/M15/M5/M1. Opportunity `mtf_alignment` 82 is the LTF BOS flag (`m1_bos` and `m5_bos` both 85), not `alignment_score`. |
| Entry timing | Sniper passed. It does not enter the quality total. |
| Reward/risk | Opportunity `rr_quality` was 100. Quality does not include reward/risk. |
| TP room | Not part of the quality total. It was not the published blocker on these scans. |
| Spread | Proven above: 97 at spread 0.424. |
| Liquidity | Opportunity liquidity was 80, from sweep presence or order-block/FVG presence in the selector. Quality liquidity is the separate v2 score 20, 65, or 85. The live value was not logged. |
| Freshness | `fvg_age_bars` was 1 then 2. Age is not a quality input. |
| Missing data | A missing order-block, FVG, or structure snapshot scores 0. A missing spread scores 50. This scan had a spread, so the neutral-50 path did not run. |
| Caps | Each component is capped at 100. The total is capped at 0–100. Structure starts at 30 rather than 0 when a snapshot exists. |

The same order block and fair-value gap can raise the liquidity component to 65 and also score on their own components. That is correlated evidence, not a second copy of the same points. It did not create the 47 by itself, and it was not changed.

## 4. Confirmed behavior versus defects

Confirmed and left unchanged:

- Quality and opportunity are different aggregates.
- The gate and the log use the same quality integer.
- Missing directional agreement on the higher timeframe can keep the weight-20 trend component low while M1/M5 still produces a BUY edge.
- Owner floor 70 rejects 47. That is the configured rule.

Not found:

- A decimal or percentage conversion error in the quality average.
- Opportunity points added into the quality total.
- A telemetry score that differs from the gate.
- A double subtraction of the session or spread penalty inside the quality total.
- A stuck or default 47.

The scan log omitted the seven factor scores. That is an observability gap, not a wrong total.

## 5. Change and tests

`explain_trade_quality` records each component score, weight, weighted points, and detail, and checks that rounding the same sum reproduces the published total. The scan log now includes `quality_explanation`. The evaluator math, the owner floor, and the opportunity weights are unchanged.

`tests/unit/test_trade_quality_explainability.py` locks:

- the owner floor at 70
- Tokyo at 00:09 UTC and spread 0.424 scoring 97, together 1,520 weighted points
- a labeled formula example whose weighted sum rounds to 47
- the logged opportunity breakdown rounding to 77, and to 76 when execution quality is 96
- consensus `round((47 + 53) / 2) = 50`

The 47 example is a formula identity. It is not a claim about the unlogged live factor split.

## 6. Why 76–77 is not 47

Opportunity weights, from the logged breakdown:

| Component | Weight | Logged value |
| --- | ---: | ---: |
| structure | 14 | 85 |
| momentum | 12 | 78 |
| consensus | 14 | 50 |
| regime_fit | 10 | 58 |
| price_action | 10 | 80 |
| liquidity | 10 | 80 |
| volatility | 8 | 74 |
| execution_quality | 10 | 97, or 96 on the later scan |
| mtf_alignment | 6 | 82 |
| rr_quality | 6 | 100 |

`7660 / 100` rounds to 77. `7650 / 100` rounds to 76. Consensus 50 is the average of quality 47 and confidence 53. Quality is 14 percent of the opportunity score, not the score itself. `opportunity_eligible` stayed false because the quality reject remains in force. An opportunity score above 70 does not authorize an order.

## 7. Is 47 trustworthy?

The integer is trustworthy as the weighted average of the seven evaluator components, and it is the value the gate used. It is not a measurement of the M1/M5 BUY edge. Until `quality_explanation` is in the logs, the five unpublished components cannot be named individually.

## 8. Remaining blockers

On the audited scans the first published blocker is quality 47 against 70. Direction, edge, and the sniper had already passed. No order was submitted. Cascade protection, the risk engine, and OMS were not reached for a new order.

## 9. Production safety

No quality weight, floor, lot size, risk percent, reward-to-risk floor, position limit, or execution safeguard was changed. This change adds a log field. It does not make 47 into a passing score.

## 10. Next step

Read one post-deploy `quality_explanation` and name the five components that make up the remaining ~31.5 points. Do not lower the floor of 70, and do not retune weights, until that split is observed. A later change that lets M1/M5 confirmation raise the M15-only structure component would be a behavior change and needs a separate owner decision.

## Limitation

No XAUUSD candle archive was used. This audit does not estimate profit or loss.
