# RC1 — Operations

## Dashboard

`/ops` (admin):

- ITE control / reliability / certification panels
- RC1 Execution Telemetry (`GET /ops/rc1-telemetry`)
- Existing alerts + audit center

## Telemetry fields (live only)

| Field | Source |
| --- | --- |
| Execution Success / Reject % | `execution_audits` submit stage (24h) |
| Risk Reject % | risk stage outcomes |
| Avg broker / gateway / validation latency | audit latency columns |
| Daily orders / volume | submit rows |
| Daily P/L | Not available from audits |
| Gateway / Railway / Cloudflare / MT5 | LiveProbeCollector |
| System Health Score | % of infra probes up |
| Alerts | Thresholds on probes + rates |

## On-call posture

- Prefer `/ops` over ad-hoc SQL.
- Treat audit rows as immutable.
- Escalate broker-side issues to Weltrade/MT5 ops — do not patch OMS.
