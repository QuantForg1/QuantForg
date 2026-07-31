# Production Execution Evidence

Observe-only collector for **real** production BUY/SELL executions from signal → broker.

## Artifacts

| File | Purpose |
| --- | --- |
| `latest_execution.md` | Human-readable latest eligible execution |
| `latest_execution.json` | Machine-readable latest package |
| `execution_history.csv` | Append-only history of eligible executions |
| `execution_history.jsonl` | Full JSON packages (deduped by validation_id) |

Certificate (when complete success):

`docs/production/certificates/Production_Acceptance_Certificate.md`

## Eligibility

Recorded only when:

- AI decision is BUY or SELL
- Broker ticket `> 0` (real MT5 ticket)
- Evidence comes from Production Validation Mode observe hooks

Never fabricates trades, tickets, or fills.

## Waiting state

If no eligible trade has occurred:

> Waiting for first eligible production execution.

## NOC

Widget **Production Acceptance** on `/admin/noc`:

- `NOT VERIFIED` → `VERIFIED`
- Latest broker ticket / execution / latency / certificate

APIs (OWNER/ADMIN):

- `GET /api/v1/ite/ops/execution-evidence`
- `GET /api/v1/ite/ops/production-acceptance`

## Hard rules

- Does not modify trading, AI, risk, OMS, MT5, or Gateway
- Payload secrets are hashed/redacted — never stored raw
- Certificate issued only when OMS + Gateway + MT5 + Broker PASS with real ticket
