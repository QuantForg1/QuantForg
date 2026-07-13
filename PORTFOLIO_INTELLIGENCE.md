# Portfolio Intelligence & Risk Laboratory

Deterministic portfolio risk analytics over **real** MT5 portfolio sync and deal/paper history.

Not an autonomous trader. Never invents market data. Never places orders.

## Principles

| Rule | Behavior |
|------|----------|
| Real data only | Positions/account from MT5 sync; VaR/CVaR/journal from deal & paper PnL |
| Unavailable ≠ invented | Missing history → explicit `status: unavailable` + reason |
| No autonomous execution | Optimizer returns recommendations only |
| Preserve stack | Existing Risk Engine, Portfolio APIs, Strategy Engine, Intelligence unchanged |
| No schema migration | Compute in-process from synced snapshots |

## Capabilities

1. **Portfolio Risk Engine** — VaR, Expected Shortfall (CVaR), exposure, leverage, margin usage, sector/currency allocation, concentration (HHI)
2. **Stress Testing** — model assumptions (flash crash, high vol, spread widening, margin compression, drawdown) + historical worst day/week from deals
3. **Portfolio Optimizer** — inverse-volatility / equal-weight fallback under max risk & max allocation constraints
4. **Correlation Engine** — pairwise Pearson on overlapping daily deal PnLs, heatmap, clusters, diversification score
5. **Trade Journal** — best/worst symbols & sessions, hold time, RR (when fields exist), win/loss rates
6. **Performance Attribution** — by symbol, strategy/comment, direction, session, week, month
7. **Explainability** — every optimizer recommendation includes reason, supporting metrics, risk impact, confidence, data source

## API (`/api/v1/portfolio-intelligence`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/dashboard` | Full laboratory snapshot |
| GET | `/risk` | Risk metrics + allocations |
| GET | `/stress` | Scenario table |
| GET | `/correlation` | Matrix / heatmap / clusters |
| GET | `/journal` | Trade journal intelligence |
| GET | `/attribution` | Return attribution |
| POST | `/optimize` | Allocation recommendations |
| POST | `/analyze` | Offline analysis from caller-supplied real snapshots |

Live endpoints require an authenticated user and attempt MT5 portfolio sync. If sync fails, responses remain structured with `portfolio_available: false` (or per-section `unavailable`) — never fabricated positions.

## Data sources

| Metric | Source |
|--------|--------|
| Equity / margin / leverage | MT5 account snapshot |
| Exposure / sector / currency | Open positions notional |
| VaR / CVaR | Historical deal PnL series (≥5 samples) |
| Correlation | Daily aggregated deal PnL by symbol (≥5 overlapping days) |
| Historical stress | Deal-day aggregates |
| Model stress | Declared % shocks on open positions (labeled as assumptions) |
| Journal / attribution | History deals + optional paper trades |
| Optimizer vols | Per-symbol deal PnL series |

## UI

Route: `/risk-lab` — institutional laboratory with gauges, allocation charts, correlation heatmap, stress table, optimizer explanations, journal, attribution.

## Related

- Pre-trade gate: `POST /risk/check` (`RiskEngine`) — unchanged
- Portfolio sync: `GET /portfolio` — unchanged
- Paper: `GET /paper/history`, `GET /paper/performance`
- Docs: `RISK_ENGINE_REPORT.md`, `STRATEGY_ENGINE.md`
