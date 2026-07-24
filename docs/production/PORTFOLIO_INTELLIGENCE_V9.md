# Institutional Portfolio Intelligence v9

Transforms QuantForg into an **AI Portfolio Manager** layer on top of existing Alpha / Validation / Performance Lab systems.

**Do not rewrite architecture. Do not duplicate correlation/risk services. No automatic capital reallocation. No martingale/grid.**

## Capabilities

| Module | Role |
|--------|------|
| Portfolio Engine | Every decision considers exposure, correlation, drawdown, PnL, vol, margin, opens |
| Capital Allocation | Dynamic shares from scores/RR/correlation (+ reserve) — advisory |
| Dynamic Risk Budget | Adaptive budget after sustained performance / drawdown |
| Optimizer | Expected return vs risk/corr/DD/margin/execution — rebalance *recommendations* |
| Capital Protection | Daily/weekly/monthly loss, symbol/corr/session/leverage — scale or block **new** exposure |
| Stress Test | High vol, low liquidity, spread, news, flash crash, gap |
| Global Regime | Risk-on/off, neutral, trend expansion/exhaustion, liquidity hunt |
| Opportunity Queue | Ranked queue with portfolio impact |
| Explainability | Permanent why-share / why-skipped |
| Long-term Analytics | 30d / 90d / 1y risk-adjusted metrics |

## Reuse (no duplication)

- Alpha `may_open_with_correlation` for correlated exposure blocks
- Existing Performance Lab / AI Validation portfolio analytics when available

## API / UI

- `GET /ite/reliability/portfolio-intelligence`
- Desk: `/portfolio-intelligence`

## Tests

`tests/unit/test_portfolio_intelligence_v9.py`
