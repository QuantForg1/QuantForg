# Institutional Research Platform v10

Continuous research, experimentation, and evidence-based improvement — **isolated from live trading**.

## Operating recommendation (before / alongside promotions)

Use QuantForg in a controlled way first:

* Demo account **or** live with **small risk**
* Collect data for **at least 2–4 weeks**
* Review: win rate, profit factor, drawdown, Sharpe, average RR, execution latency, slippage, AI calibration

The Research Platform encodes this as dashboard guidance and continuous-improvement insights. **No auto-deploy to Production.**

## Capabilities

| Module | Behaviour |
|--------|-----------|
| Research Workspace | Isolated scoring/indicator/filter/model variants |
| Experiment Manager | Draft → Running → Completed → Archived |
| Backtesting | Historical, walk-forward, OOS metrics; syncs into existing backtest-vs-live store |
| Optimization Studio | Parameter search recorded; **never auto-applied** |
| Model Registry | Versions + approval; promotion is explicit |
| Institutional Reporting | Daily/weekly/monthly + CSV / PDF-text export |
| Audit Trail | Permanent user/timestamp/old/new/reason (secrets redacted) |
| Promotion Workflow | Development → Research → Paper → Demo → Limited Live → Production |
| Continuous Improvement | Advisory insights only |
| Docs generation | Markdown for experiments / models / optimizations / config changes |

## Reuse (no duplication)

- `production_hardening.backtest_live` for live vs backtest comparison upserts
- AI Validation / Performance Lab / Portfolio Intelligence snapshots for reports

## API / UI

- `GET /ite/reliability/research-platform`
- `POST /ite/reliability/research-platform/experiments`
- `POST /ite/reliability/research-platform/reports/{daily|weekly|monthly}`
- Desk: `/research-platform`

## Hard locks

- `auto_promote_to_production = False`
- `auto_apply_optimizations = False`
- `research_isolated_from_live = True`

## Tests

`tests/unit/test_research_platform_v10.py`
