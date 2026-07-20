# RC2 Performance Report

Generated during RC2 final certification. Values marked **Not measured** were not observed on a production host in this pass.

## Method

| Source | What it covers |
| --- | --- |
| Unit / CI runtime | Local test latency only |
| Next.js production build | Route compilation; Turbopack does not print First Load JS |
| LiveProbeCollector / /ops/rc1-telemetry | Gateway / Railway / Cloudflare / MT5 availability + audit-derived latencies when live |
| Supabase advisors | DB performance advisories |

## Metrics

| Metric | Result | Status |
| --- | --- | --- |
| API latency (p50/p95 production) | Not measured on production host this pass | WARN |
| Gateway latency | Available live via execution_audits.gateway_latency_ms + /ops/rc1-telemetry | PASS (instrumented) |
| Broker latency | Available live via submit/manage audit latency_ms | PASS (instrumented) |
| Database latency | Probe field database_latency_ms when Supabase configured | PASS (instrumented) |
| Largest SQL query | Not profiled with pg_stat_statements this pass | WARN |
| Largest frontend bundle | Next 16 Turbopack build emits no size table | WARN |
| Slowest page | Not measured (no Lighthouse/prod RUM run this pass) | WARN |
| Frontend www | HTTP 200 at certification |
| Railway API health | HTTP 200 (quantforg-production.up.railway.app) |
| api.quantforg.com | **Retired** — Railway is canonical (see [api-hostname.md](api-hostname.md)) |

## Instrumentation present (code)

- Execution audits store broker + gateway latency per request stage
- LiveProbeCollector probes gateway /health, Railway /health, Cloudflare markers, MT5 connection
- RC1/RC2 ops telemetry aggregates 24h audit latencies and infra availability

## Required for V1.0 performance sign-off

1. Capture Railway metrics (CPU/memory) for 24h
2. Enable pg_stat_statements and list top 10 queries by mean time
3. Run Lighthouse (or Web Vitals) against production frontend for eight desks
4. Export Next bundle analyzer once (webpack mode) if Turbopack remains size-blind
