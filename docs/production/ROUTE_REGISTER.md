# QuantForg route register

Generated 17 Nov 2026 from `frontend/src/app` (336 page files, dynamic segments included). Policy (PR: customer route allowlist): customers can open **Customer desk** routes only. Any other in-app URL redirects to `/dashboard`. Owner and admin keep every page, and server-side RBAC is unchanged. Nothing was deleted: retiring a page needs a dependency check and an owner decision, and the redirect already removes it from customer journeys.

| Class | Pages |
|---|---|
| Customer desk | 31 |
| Public / auth / billing | 23 |
| Admin (owner-gated) | 16 |
| Operator desk (owner) | 49 |
| Internal / research / legacy (owner only; linked) | 101 |
| Unlinked legacy (owner only; candidate for retirement) | 112 |
| Redirect stub (legacy URL kept) | 4 |

## Customer desk (31)

`/ai-robot`, `/ai-trading-intelligence`, `/analytics`, `/book`, `/broker`, `/dashboard`, `/get-started`, `/history`, `/intelligence`, `/journal`, `/journal/analytics`, `/journal/orders`, `/markets`, `/notifications`, `/orders`, `/portfolio`, `/positions`, `/profile`, `/research`, `/risk-center`, `/robot-control-center`, `/settings`, `/shortcuts`, `/signals`, `/strategy`, `/support`, `/symbols/[code]`, `/trade-replay`, `/trading-journal`, `/wallet`, `/whats-new`

## Public / auth / billing (23)

`/auth/callback`, `/billing/checkout`, `/billing/invoices`, `/billing/invoices/[orderCode]`, `/billing/return`, `/contact`, `/contact/success`, `/forgot-password`, `/live`, `/live-alerts`, `/live-execution-explain`, `/live-learning-program`, `/login`, `/mfa`, `/pricing`, `/privacy`, `/purchase`, `/purchase/success`, `/register`, `/reset-password`, `/risk-disclosure`, `/terms`, `/verify-email`

## Admin (owner-gated) (16)

`/admin`, `/admin/brokers`, `/admin/continuous-improvement`, `/admin/control`, `/admin/customer-ops`, `/admin/enterprise`, `/admin/live-trading`, `/admin/live-trading-evidence`, `/admin/multi-account`, `/admin/noc`, `/admin/operations`, `/admin/plans`, `/admin/reliability`, `/admin/support`, `/admin/users`, `/admin/users/[id]`

## Operator desk (owner) (49)

`/account-orchestration`, `/api-inspector`, `/auto-trading`, `/autonomous-trading`, `/autonomy-control`, `/decision-approvals`, `/decision-intelligence`, `/execution-intelligence`, `/execution-optimization`, `/execution/diagnostics`, `/executions`, `/executive-dashboard`, `/executive-home`, `/gateway`, `/governance`, `/incident-center`, `/institutional-alpha`, `/institutional-reports`, `/intelligence-center`, `/logs`, `/market-scanner`, `/mission-control`, `/monitoring`, `/operations`, `/operator-home`, `/ops`, `/portfolio-optimization`, `/predictive-market-intelligence`, `/predictive-risk`, `/quant-research`, `/research-data`, `/research-governance`, `/research-leaderboard`, `/risk-automation`, `/risk-lab`, `/signal-center`, `/signal-intelligence`, `/strategy-analytics`, `/strategy-backtesting`, `/strategy-diagnostics`, `/strategy-factory`, `/strategy-intelligence-center`, `/strategy-lifecycle`, `/strategy-optimization`, `/strategy-performance`, `/strategy-research`, `/symbol-management`, `/trade-intelligence`, `/trading-kernel`

## Internal / research / legacy (owner only; linked) (101)

`/adaptive-opportunity`, `/adaptive-scalping-intelligence`, `/ai`, `/ai-coach`, `/ai-quant-copilot`, `/ai-quant-scientist`, `/ai-scalping`, `/ai-signals`, `/ai-trade-replay`, `/ai-validation`, `/alerts`, `/allocation`, `/alpha-engine`, `/alpha-factory`, `/audit-governance`, `/automatic-production-acceptance`, `/candidate-validation`, `/continuous-validation`, `/daily-reports`, `/decision-engine`, `/economic-calendar`, `/ecosystem`, `/execution-quality-suite`, `/execution-timeline`, `/experimental-threshold`, `/exposure`, `/first-execution-evidence`, `/incidents`, `/institutional-control-center`, `/institutional-control-plane`, `/institutional-data-warehouse`, `/institutional-decision`, `/institutional-edge-engine`, `/institutional-experimentation`, `/institutional-observability`, `/institutional-release`, `/institutional-research-lab`, `/institutional-research-lab/experiments`, `/institutional-risk-analytics`, `/institutional-simulation`, `/institutional-strategy-lifecycle`, `/institutional-validation-program`, `/integration-sprint-v1`, `/integrations`, `/intelligence-platform`, `/market-intelligence`, `/market-regime-intelligence`, `/micro-account-analyzer`, `/mt5`, `/multi-agent-ai`, `/operations-runbook`, `/opportunity-timeline`, `/order-monitor`, `/organizations`, `/paper`, `/performance`, `/performance-analytics`, `/performance-intelligence`, `/performance-lab`, `/portfolio-analytics`, `/portfolio-heatmap`, `/portfolio-intelligence`, `/production-acceptance`, `/production-acceptance-countdown`, `/production-acceptance-test`, `/production-burnin`, `/production-readiness`, `/production-readiness-certification`, `/production-readiness-review`, `/production-reliability`, `/production-replay`, `/production-validation`, `/quant-knowledge-graph`, `/quantforg-canonical-data`, `/quantforg-certification`, `/quantforg-decision-intelligence`, `/quantforg-event-mesh`, `/quantforg-operations-center`, `/quantforg-paper-trading`, `/quantforg-portfolio-manager`, `/quantforg-strategy-factory`, `/quantforg-strategy-factory/approvals`, `/quantforg-strategy-marketplace`, `/rc1`, `/real-market-intelligence-platform`, `/reliability-engineering-suite`, `/replay-evidence-lab`, `/reports`, `/research-lab`, `/research-platform`, `/research-validation`, `/scalping-ai-v2`, `/screeners`, `/session-readiness`, `/strategy-lab`, `/strategy-leaderboard`, `/threshold-performance-analysis`, `/threshold-promotion`, `/trading-brain-v3`, `/trading-operations-center`, `/witness-health`

## Unlinked legacy (owner only; candidate for retirement) (112)

`/.`, `/ai-quant-copilot/ask`, `/ai-quant-copilot/evidence`, `/ai-quant-copilot/history`, `/ai-quant-copilot/investigations`, `/ai-quant-copilot/recommendations`, `/ai-quant-copilot/reports`, `/ai-quant-copilot/timeline`, `/ai-quant-scientist/compare`, `/ai-quant-scientist/explain`, `/ai-quant-scientist/feed`, `/ai-quant-scientist/patterns`, `/ai-quant-scientist/recommendations`, `/ai-quant-scientist/reports`, `/backtesting`, `/broker-certification`, `/broker-compatibility`, `/broker-connectivity`, `/cloud-ops`, `/continuous-validation/confidence`, `/continuous-validation/drift`, `/continuous-validation/evidence`, `/continuous-validation/replay-vs-live`, `/continuous-validation/reports`, `/execution-quality-suite/broker`, `/execution-quality-suite/latency`, `/execution-quality-suite/reports`, `/execution-quality-suite/score`, `/execution-quality-suite/slippage`, `/execution-quality-suite/timeline`, `/institutional-control-plane/dependencies`, `/institutional-control-plane/evidence`, `/institutional-control-plane/health`, `/institutional-control-plane/reports`, `/institutional-control-plane/timeline`, `/institutional-experimentation/comparison`, `/institutional-experimentation/decisions`, `/institutional-experimentation/evidence`, `/institutional-experimentation/hypothesis`, `/institutional-experimentation/reports`, `/institutional-release/approvals`, `/institutional-release/reports`, `/institutional-release/rollbacks`, `/institutional-release/timeline`, `/institutional-research-lab/benchmark`, `/institutional-research-lab/experiments/[id]`, `/institutional-research-lab/jobs`, `/institutional-research-lab/leaderboard`, `/institutional-research-lab/reports`, `/institutional-risk-analytics/correlation`, `/institutional-risk-analytics/drawdown`, `/institutional-risk-analytics/exposure`, `/institutional-risk-analytics/reports`, `/institutional-risk-analytics/stress`, `/institutional-simulation/explorer`, `/institutional-simulation/monte-carlo`, `/institutional-simulation/reports`, `/institutional-simulation/scenarios`, `/institutional-simulation/stress`, `/institutional-simulation/walk-forward`, `/institutional-strategy-lifecycle/evidence`, `/institutional-strategy-lifecycle/health`, `/institutional-strategy-lifecycle/reports`, `/institutional-strategy-lifecycle/timeline`, `/institutional-strategy-lifecycle/versions`, `/quant-ai`, `/quant-knowledge-graph/evidence`, `/quant-knowledge-graph/relationships`, `/quant-knowledge-graph/root-cause`, `/quant-studio`, `/quantforg-canonical-data/models`, `/quantforg-canonical-data/relationships`, `/quantforg-canonical-data/timeline`, `/quantforg-certification/blockers`, `/quantforg-certification/evidence`, `/quantforg-certification/readiness`, `/quantforg-certification/reports`, `/quantforg-certification/timeline`, `/quantforg-decision-intelligence/evidence`, `/quantforg-decision-intelligence/executive`, `/quantforg-decision-intelligence/recommendations`, `/quantforg-decision-intelligence/tradeoffs`, `/quantforg-event-mesh/correlation`, `/quantforg-event-mesh/stream`, `/quantforg-event-mesh/timeline`, `/quantforg-operations-center/brief`, `/quantforg-operations-center/evidence`, `/quantforg-operations-center/queue`, `/quantforg-operations-center/recommendations`, `/quantforg-operations-center/reports`, `/quantforg-paper-trading/evidence`, `/quantforg-paper-trading/explorer`, `/quantforg-paper-trading/graduation`, `/quantforg-paper-trading/reports`, `/quantforg-paper-trading/timeline`, `/quantforg-portfolio-manager/allocation`, `/quantforg-portfolio-manager/diversification`, `/quantforg-portfolio-manager/ranking`, `/quantforg-portfolio-manager/reports`, `/quantforg-strategy-factory/evidence`, `/quantforg-strategy-factory/pipeline`, `/quantforg-strategy-factory/reports`, `/quantforg-strategy-factory/workspace`, `/quantforg-strategy-marketplace/comparison`, `/quantforg-strategy-marketplace/evidence`, `/quantforg-strategy-marketplace/explorer`, `/quantforg-strategy-marketplace/reports`, `/reliability-engineering-suite/failures`, `/reliability-engineering-suite/health`, `/reliability-engineering-suite/recovery`, `/reliability-engineering-suite/reports`, `/walkforward`

## Redirect stub (legacy URL kept) (4)

`/brokers`, `/counsel`, `/execution-intel`, `/risk`

## Next steps

1. **Done:** visual acceptance of the customer desks on desktop and mobile using the signed-in owner session (see the tracker).
2. **Unlinked legacy pages:** each needs owner confirmation before deletion. Some still back test fixtures or release notes.
3. **Internal / research pages:** fold the duplicated families (`production-*`, `institutional-*`, `quantforg-*`, numbered phase desks) into the admin portal over time. The backend endpoints behind them must stay owner/admin-gated (tracked in the security audit).

## Retirement candidates (dependency check, 17 Nov)

Each unlinked legacy page was checked for test references (Python suites) and for components it imports that no other file uses (those become dead code if the page is removed). Nothing was deleted. Retirement needs the owner's go-ahead.

| Route | Exclusive components | Test references | Status |
|---|---|---|---|
| `/.` | 3 | 572 | pinned by tests: update tests first |
| `/ai-quant-copilot/ask` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/evidence` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/history` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/investigations` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/recommendations` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/reports` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-copilot/timeline` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/compare` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/explain` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/feed` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/patterns` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/recommendations` | 0 | 0 | safe to retire after owner OK |
| `/ai-quant-scientist/reports` | 0 | 0 | safe to retire after owner OK |
| `/backtesting` | 0 | 1 | pinned by tests: update tests first |
| `/broker-certification` | 0 | 0 | safe to retire after owner OK |
| `/broker-compatibility` | 0 | 0 | safe to retire after owner OK |
| `/broker-connectivity` | 0 | 0 | safe to retire after owner OK |
| `/cloud-ops` | 0 | 0 | safe to retire after owner OK |
| `/continuous-validation/confidence` | 0 | 0 | safe to retire after owner OK |
| `/continuous-validation/drift` | 0 | 0 | safe to retire after owner OK |
| `/continuous-validation/evidence` | 0 | 0 | safe to retire after owner OK |
| `/continuous-validation/replay-vs-live` | 0 | 0 | safe to retire after owner OK |
| `/continuous-validation/reports` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/broker` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/latency` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/reports` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/score` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/slippage` | 0 | 0 | safe to retire after owner OK |
| `/execution-quality-suite/timeline` | 0 | 0 | safe to retire after owner OK |
| `/institutional-control-plane/dependencies` | 0 | 0 | safe to retire after owner OK |
| `/institutional-control-plane/evidence` | 0 | 0 | safe to retire after owner OK |
| `/institutional-control-plane/health` | 0 | 0 | safe to retire after owner OK |
| `/institutional-control-plane/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-control-plane/timeline` | 0 | 0 | safe to retire after owner OK |
| `/institutional-experimentation/comparison` | 0 | 0 | safe to retire after owner OK |
| `/institutional-experimentation/decisions` | 0 | 0 | safe to retire after owner OK |
| `/institutional-experimentation/evidence` | 0 | 0 | safe to retire after owner OK |
| `/institutional-experimentation/hypothesis` | 0 | 0 | safe to retire after owner OK |
| `/institutional-experimentation/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-release/approvals` | 0 | 0 | safe to retire after owner OK |
| `/institutional-release/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-release/rollbacks` | 0 | 0 | safe to retire after owner OK |
| `/institutional-release/timeline` | 0 | 0 | safe to retire after owner OK |
| `/institutional-research-lab/benchmark` | 0 | 0 | safe to retire after owner OK |
| `/institutional-research-lab/experiments/[id]` | 0 | 0 | safe to retire after owner OK |
| `/institutional-research-lab/jobs` | 0 | 0 | safe to retire after owner OK |
| `/institutional-research-lab/leaderboard` | 0 | 0 | safe to retire after owner OK |
| `/institutional-research-lab/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-risk-analytics/correlation` | 0 | 0 | safe to retire after owner OK |
| `/institutional-risk-analytics/drawdown` | 0 | 0 | safe to retire after owner OK |
| `/institutional-risk-analytics/exposure` | 0 | 0 | safe to retire after owner OK |
| `/institutional-risk-analytics/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-risk-analytics/stress` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/explorer` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/monte-carlo` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/scenarios` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/stress` | 0 | 0 | safe to retire after owner OK |
| `/institutional-simulation/walk-forward` | 0 | 0 | safe to retire after owner OK |
| `/institutional-strategy-lifecycle/evidence` | 0 | 0 | safe to retire after owner OK |
| `/institutional-strategy-lifecycle/health` | 0 | 0 | safe to retire after owner OK |
| `/institutional-strategy-lifecycle/reports` | 0 | 0 | safe to retire after owner OK |
| `/institutional-strategy-lifecycle/timeline` | 0 | 0 | safe to retire after owner OK |
| `/institutional-strategy-lifecycle/versions` | 0 | 0 | safe to retire after owner OK |
| `/quant-ai` | 0 | 0 | safe to retire after owner OK |
| `/quant-knowledge-graph/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quant-knowledge-graph/relationships` | 0 | 0 | safe to retire after owner OK |
| `/quant-knowledge-graph/root-cause` | 0 | 0 | safe to retire after owner OK |
| `/quant-studio` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-canonical-data/models` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-canonical-data/relationships` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-canonical-data/timeline` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-certification/blockers` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-certification/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-certification/readiness` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-certification/reports` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-certification/timeline` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-decision-intelligence/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-decision-intelligence/executive` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-decision-intelligence/recommendations` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-decision-intelligence/tradeoffs` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-event-mesh/correlation` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-event-mesh/stream` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-event-mesh/timeline` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-operations-center/brief` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-operations-center/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-operations-center/queue` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-operations-center/recommendations` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-operations-center/reports` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-paper-trading/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-paper-trading/explorer` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-paper-trading/graduation` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-paper-trading/reports` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-paper-trading/timeline` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-portfolio-manager/allocation` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-portfolio-manager/diversification` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-portfolio-manager/ranking` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-portfolio-manager/reports` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-factory/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-factory/pipeline` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-factory/reports` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-factory/workspace` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-marketplace/comparison` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-marketplace/evidence` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-marketplace/explorer` | 0 | 0 | safe to retire after owner OK |
| `/quantforg-strategy-marketplace/reports` | 0 | 0 | safe to retire after owner OK |
| `/reliability-engineering-suite/failures` | 0 | 0 | safe to retire after owner OK |
| `/reliability-engineering-suite/health` | 0 | 0 | safe to retire after owner OK |
| `/reliability-engineering-suite/recovery` | 0 | 0 | safe to retire after owner OK |
| `/reliability-engineering-suite/reports` | 0 | 0 | safe to retire after owner OK |
| `/walkforward` | 0 | 4 | pinned by tests: update tests first |
