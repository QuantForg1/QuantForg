# AI Validation & Performance Optimization v7

Extends QuantForg with validation and profitability analytics. **No architecture rewrite. Existing safeguards preserved. Trading rules are never auto-changed.**

## Capabilities

| Area | Behaviour |
|------|-----------|
| Shadow AI | Second independent evaluation before live path; disagreements logged; primary engine used unless `shadow_veto_enabled` |
| Strategy performance | Scalping / Intraday / Swing — win rate, RR, avg profit/loss, profit factor, Sharpe, holding time |
| Weight optimizer | Gradual multipliers for trend, liquidity, momentum, volatility, session, BOS, CHOCH, FVG, Order Block — logged |
| Execution quality | Signal / AI / OMS / Gateway / MT5 / Broker latency + bottleneck |
| Slippage | Expected vs actual entry/exit; avg / worst / best; recommendations |
| Portfolio | Daily/weekly/monthly return, max/current DD, exposure by symbol & asset class, correlation |
| Opportunity history | Top 10/day with traded/skipped + replay |
| Benchmarks | QuantForg vs Buy&Hold / SMA crossover / baseline |
| Alerts | Win-rate drop, drawdown, slippage/latency spikes, consecutive losses — **observational only** (no auto halt) |

## Package

`app/domain/institutional_trading/ai_validation/`

## API / UI

- `GET /ite/reliability/ai-validation?replay_day=YYYY-MM-DD`
- Desk: `/ai-validation` (OWNER/ADMIN)

## Wiring

- `InstitutionalIteRuntime._run_cycle` runs Shadow AI after primary decision
- Post-OMS hooks record execution quality + entry slippage
- Alpha scan records daily opportunity top-10
- Ranking applies optimizer multipliers on top of v6 learning weights

## Tests

`tests/unit/test_ai_validation_v7.py`
