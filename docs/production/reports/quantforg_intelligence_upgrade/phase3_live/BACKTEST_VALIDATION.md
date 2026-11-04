# Backtest / offline validation

## Scope

Full multi-year walk-forward with tick-level costs was **not** re-run in this PR (no new candle dump in-repo for this session). Validation used:

1. **Unit regressions** — Phase 3 SOE intelligence + existing orchestration suites (52 related tests green locally).
2. **Counterfactual** on Phase 2 attributed TC losers with mixed-LTF factor reconstruction — see `offline_counterfactual.json`.
3. **Sensitivity** — NY solo bars; chase gate smoke; regime rank breakout&gt;TC.

## Counterfactual result

| Ticket | Strategy | Net | Phase 3 blocked? |
|---:|---|---:|:---:|
| 683675942 | trend_continuation | -$2.00 | Yes |
| 683682967 | trend_continuation | -$1.55 | Yes |

Avoided in counterfactual: **$3.55** (illustrative only).

## Cost assumptions

Gates fire **before** OMS; spread/RR floors already in SOE evidence gate (`MIN_NET_REWARD_RISK=0.20`, elevated-spread check). Commission/swap remain broker-truth on close attribution.

## Activation rule

Improvements that failed unit validation were not activated. Speculative BE/trail changes were **not** shipped (insufficient OOS proof).
