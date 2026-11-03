# QuantForg Phase 6 — Strategy Intelligence & Profitability Optimization

## Root cause of missed opportunities

| Cause | Class | Action |
|---|---|---|
| Owner net RR double-counted spread (SL already buffered by spread, then spread added again in `net_reward_risk`) | **Software defect** | Fixed — `spread_already_in_stop` / `stop_includes_spread_buffer` |
| Gold regime ATR thresholds 0.4 / 1.5 never classified breakout/expansion on XAUUSD | **Calibration defect** | Fixed — asset-class bands via `classify_atr_band_thresholds` |
| Correlated pack passers always hit solo Q≥82 bar | **Collaboration gap** | Fixed — pack agreement (≥2 passers) may clear at Q≥76 |
| Score-factor advisory proxies could invent strong disagreement | **False veto risk** | Fixed — strong disagreement requires real engines |
| Gross vs net TP-room asymmetry under owner floor ≥1.50 | **Inconsistency** | Fixed — TP room uses net RR when floor ≥1 |
| ATR% &lt; 0.08 / Q &lt; 75 / no edge / genuine net RR &lt; 1.50 | **Legitimate NO_TRADE** | Unchanged — owner floors preserved |
| Shared ATR hard min across five-pack | **Intentional** | Unchanged — not loosened |

## Changes by strategy

All five remain specialization filters over SCALPING_V1. No per-strategy threshold loosening.

| Strategy | Change |
|---|---|
| smc_scalping | Benefits from RR / pack-agreement / regime fixes |
| trend_continuation | Same + pack agreement with trend cluster |
| breakout_scalping | Gold regime can now reach `breakout` at realistic ATR%; band filter unchanged |
| range_mean_reversion | Compression/range still regime-gated; gold low-band compression correct |
| momentum_scalping | Same as trend cluster pack agreement |

## Validation evidence

- Unit: `tests/unit/test_phase6_strategy_intelligence.py` (RR double-count, owner TP, gold regime, advisory, SOE v1.4.0)
- Updated: `test_strategy_collaboration_v11.py` (version + real-engine disagreement)
- Owner floors Q75 / RR 1.50 / preferred 2.00 / M1 OFF / max lot 0.01 unchanged

## Strategy-by-strategy matched performance

Unchanged from Phase 5 until new attributed closes accumulate:

- Five-pack matched closed: **0**
- ITE historical: n=30, +$18.14, PF 1.42 (no size increase)
- M1 historical: n=32, −$23.18, PF 0.52 (new LIVE entries remain OFF)

Do **not** claim profitability from this phase.

## Remaining limitations

1. Dead-tape ATR% &lt; 0.08 and Q &lt; 75 remain correct rejects.
2. Insufficient five-pack closed sample for expectancy claims.
3. Walk-forward / out-of-sample broker campaigns still required before any profitability assertion.
4. M5 vs M15 ATR gate series calibration remains a future evidence task — hard min **not** lowered in Phase 6.
