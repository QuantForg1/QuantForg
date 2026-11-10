# Phase 7 — Ops UI + soak acceptance

**Baseline API:** `c38c2731`  
**Gates:** dispatch=false, live_submit=false

## UI

| Item | Status | Label |
|---|---|---|
| `/admin/multi-account` Owner page | Implemented | Locally verified |
| Metric cards (queue/workers/brokers/latency) | Implemented | Locally verified |
| Refresh observe-only | Enforced in API + UI copy | Automated test verified |
| Customer cannot access owner summary | Designated-owner gate | Automated test verified |

## Soak

| Item | Status | Label |
|---|---|---|
| Sustained concurrent soak ≥15s | `test_sustained_concurrent_soak_*` | Automated test verified |
| PG SKIP LOCKED helper present | `claim_next_skip_locked` | Automated test verified (fallback) |
| Real staging PG soak | — | **Blocked** (no staging soak environment in this session) |

## Demo readiness

| Item | Status | Label |
|---|---|---|
| Worker agent register/heartbeat/claim APIs | Present from prior phases | Locally verified |
| Real MT5 demo authentication | — | **Blocked** (no demo credentials) |
| Demo order execution | — | **Blocked** / Not authorized |

## Safety

Flags remain OFF. No Production orders. Weltrade LIVE preserved. P7 10% preference must remain after deploy verify.
