# Execution Intelligence & Trade Lifecycle Manager

Additive analytics layer over QuantForg’s existing Execution Gateway, safety checks, paper fills, and MT5 connection state.

**Never** places orders. **Never** flips `EXECUTION_ENABLED`. **Never** invents market data.

## Lifecycle states

`Draft → Validated → Risk Approved → Submitted → Accepted → Rejected → Filled → Partially Filled → Modified → Cancelled → Closed`

- Transitions archived in-process (`LifecycleStore`)
- Reconstructed from real `execution_attempts` + `execution_decisions`
- Manual `POST /execution-intelligence/lifecycle/observe` for operator-observed events

## APIs (`/api/v1/execution-intelligence`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/dashboard` | Timeline, metrics, checklist, broker, risk decisions |
| GET | `/lifecycle` | Lifecycle history |
| GET | `/lifecycle/{request_id}` | Single record |
| POST | `/lifecycle/observe` | Record real transition |
| POST | `/checklist` | Pre-trade blockers (deterministic) |
| GET | `/analytics` | Latency, fill/reject, slippage, quality, duration |
| GET | `/post-trade` | Completed trade explainability (paper) |
| POST | `/post-trade/analyze` | Analyze caller-supplied trade rows |
| GET | `/broker` | Connection, heartbeat, latency, disconnect, reconnect history |

## Pre-trade checklist

Facts (unknown → `unavailable`, never invented):

- Broker connected
- Market open
- Risk passed
- Margin sufficient
- Strategy signal valid
- Execution enabled (read from settings only)

## Analytics sources

| Metric | Source |
|--------|--------|
| Fill / reject rates | `execution_attempts.outcome` |
| Latency | `latency_ms` on attempts when present |
| Slippage | Paper trade slippage / price pairs |
| Duration | `submitted_at` → `filled_at` when both exist |
| Broker heartbeat / latency | MT5 connection entity |

## UI

`/execution-intel` — institutional dashboard for lifecycle, checklist, metrics, broker health, post-trade.

## Related

- Live path: `POST /execution/check`, `POST /execution/submit` (unchanged)
- Paper: `/paper/*`
- Risk: `POST /risk/check`
- Docs: `PORTFOLIO_INTELLIGENCE.md`, `STRATEGY_ENGINE.md`
