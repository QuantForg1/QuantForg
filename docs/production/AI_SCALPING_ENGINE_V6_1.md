# Institutional AI Scalping Engine v6.1 — Live Execution Hardening

Built on **v6.0** baseline. Does **not** replace the AI strategy. Does **not**
lower quality thresholds. Does **not** raise risk.

## Additions

| Area | Behaviour |
|------|-----------|
| Adaptive regimes | Trending / ranging / high-vol / low-vol adjust RR floor, trail, hold, partial — safety never loosened |
| Spread protection | Reject when spread > max **or** > configured % of ATR |
| Slippage protection | Measure requested vs fill; journal; pause new entries on abnormal burst |
| Execution quality | Rolling fill / reject / partial / requote / latency stats |
| Vol-adjusted sizing | Optional; may only **reduce** risk% in high vol; never martingale/grid |
| Post-trade analytics | R, MAE, MFE, hold time, spread, slippage, latency → journal |
| Live health | Gateway / broker / MT5 / OMS / market data / latency |
| Self-protection | Pause **new** entries on DD / reject burst / slip burst / gateway instability; existing positions still managed |
| Dashboard | Read-only win rate, avg R, PF, hold, latency, execution success |

## Tests

`tests/unit/test_ai_scalping_v6_1_hardening.py` plus prior v5/v6 suites.
