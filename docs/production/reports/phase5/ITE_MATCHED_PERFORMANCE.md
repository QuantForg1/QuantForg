# Phase 5 — ITE matched broker performance (separate from SOE five-pack)

**Source:** Phase-4 gateway reconcile (`docs/production/reports/phase4/m1_position_attribution.json`)  
**Method:** magic `260720`, XAUUSD, group by `position_id`, classify via **entry** comment `ite:*`  
**Costs:** profit + commission + swap + fee from MT5 deals

## Results (30d closed)

| Metric | Value |
|---|---|
| Closed positions | 30 |
| Net P&amp;L after costs | **+18.14 USD** |
| Profit factor | 1.42 |
| Expectancy | +0.60 |
| Win rate | 46.7% (14W / 16L) |
| Average winner | +4.35 |
| Average loser | -2.68 |
| Max DD (closed curve) | 12.12 |

## Interpretation (no size increase)

- Positive sample is **small** (n=30) and **not** a profitability certificate for indefinite LIVE scaling.
- Competing correctly with SOE: ITE primary path vs five-pack SOE winners — five-pack had **0** OMS accepts in the Phase-4 window; ITE historical `ite:*` book is the only positive matched cohort here.
- Regimes / walk-forward: not re-simulated in Phase-5; do **not** auto-increase lot or risk.
- Attribution going forward: ticket-keyed store binds `ite_primary` / SOE `strategy_id` at fill so closed stats no longer depend on exit comments.

## Owner constraint

Preserve max lot 0.01 and 20% planned risk ceiling — no ITE size uplift in this phase.
