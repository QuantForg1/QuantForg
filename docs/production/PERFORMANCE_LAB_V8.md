# Live Performance Lab v8

Continuous experimentation and validation using live results. **No architecture rewrite. Challenger never executes. Recommendations never auto-apply. Trading logic unchanged without measurable evidence + human gate.**

## Capabilities

| Area | Behaviour |
|------|-----------|
| Champion vs Challenger | Champion = production (may trade). Challenger = candidate weights (observe only) |
| Trade Replay Studio | Snapshot, structure, BOS/CHOCH/FVG/OB, AI reasoning, entry/exit/SL/TP/trail frames |
| Confidence calibration | Predicted confidence bins vs realized win rate; over/under flags |
| Opportunity outcome DB | Every evaluation including skips + hypothetical outcome |
| Strategy comparison | Scalping / Intraday / Swing with symbol/session/regime filters |
| Symbol intelligence | Best/worst, sessions, slippage/latency/spread rankings |
| Portfolio heatmap | Exposure, correlation, risk, confidence, unrealized/realized PnL |
| Adaptive recommendations | Advisory text only |
| Explainability | Permanent human-readable why-* (extends v6 store) |

## Package

`app/domain/institutional_trading/performance_lab/`

## API / UI

- `GET /ite/reliability/performance-lab`
- Desk: `/performance-lab`

## Hard locks

- `challenger_may_execute = False`
- Duel store raises if `challenger_executed=True`
- Recommendation `auto_applied` always false

## Tests

`tests/unit/test_performance_lab_v8.py`
