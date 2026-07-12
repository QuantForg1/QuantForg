# Operations

**Release:** QuantForg v1.0.0-rc.1  

Operational surfaces are provided by the Operations & Observability Platform. Trading logic is out of scope for ops day-2 work.

## Day-2 dashboards

| Endpoint | Use |
|----------|-----|
| `GET /api/v1/ops/dashboard` | System, broker, MT5, API, DB, queue, jobs |
| `GET /api/v1/ops/metrics` | Latency, errors, throughput, cache, jobs |
| `GET /api/v1/ops/alerts` | Rules + open/recent alerts |
| `GET /api/v1/ops/audit` | Auth / broker / strategy / risk / execution / paper events |
| `GET /api/v1/metrics` | Public metrics snapshot |

## Alert rules (default)

| Code | Severity | Meaning |
|------|----------|---------|
| `mt5_disconnected` | critical | MT5 client not connected |
| `broker_unhealthy` | critical | Broker connection unhealthy |
| `risk_engine_failures` | critical | Risk failure signal |
| `strategy_failures` | warning | Strategy failure signal |
| `migration_failures` | critical | Migration failure signal |

Severities: `info`, `warning`, `critical`.

## Runbooks (short)

### MT5 disconnected

1. Check `GET /api/v1/mt5/status` and ops dashboard MT5 component.  
2. Confirm `MT5_ENABLED` / mock vs live path.  
3. Reconnect via `POST /api/v1/mt5/connect` only in controlled environments.  
4. Do **not** enable execution to “test” connectivity.

### Broker unhealthy

1. Inspect `GET /api/v1/brokers/{id}/health` and diagnostics.  
2. Review reconnect policy / heartbeat latency.  
3. Open alert should appear under `/ops/alerts` when rule fires.

### API / DB degradation

1. Hit `/health/ready` and `/metrics`.  
2. Check Postgres pool and Redis.  
3. Review structured logs (`structlog`) for request IDs.

### Migration failure

1. Stop rollout.  
2. Inspect migration runner logs.  
3. Set ops failure signal / acknowledge critical alert.  
4. Roll back with down scripts (see `BACKUP_RECOVERY.md`).

## Logging

- Formats: console (dev) or JSON (prod) via `LOG_FORMAT` / `LOG_JSON`  
- Correlate with `X-Request-ID`  

## Safety invariants for operators

- `EXECUTION_ENABLED` must stay **false** on RC1.  
- Never call live `order_send` outside reviewed enablement.  
- AI features are not present — ignore any future AI flags.

Full module report: `OPERATIONS_PLATFORM_REPORT.md`.
