# Broker Certification Report

Certification advances ecosystem brokers from **Pending Session** to **Certified** using **only real MetaTrader 5 sessions**. No simulated broker data. No DB schema changes. Existing APIs unchanged — additive routes under `/broker-connectivity/certification/*`.

## Workflow states

1. Not Tested  
2. Pending Session  
3. Connected  
4. Sync Verified  
5. Market Data Verified  
6. Paper Trading Verified  
7. Execution Check Verified  
8. Certified  

Side path: **Failed** (invalid credentials / hard probe errors).

## Certification report (per broker)

| Field | Source |
|-------|--------|
| Server name | Live MT5 health |
| MT5 build | Live terminal_build |
| Hedging/Netting mode | `null` until exposed by account snapshot (never invented) |
| Account currency | Live balances |
| Leverage | Live balances |
| Symbols available | Live symbols count |
| Execution latency | Trading gate probe latency |
| Quote latency | Quotes probe latency |
| Heartbeat stability | Heartbeat/ping probe |
| Last certification time | Stored on successful Certified |

## History

In-process store (same pattern as Execution Intelligence lifecycle):

- Date, Broker, Result, Failure reason, Tester, Diagnostics, Report snapshot

## Diagnostics

Classified from live probe reasons:

- wrong_server  
- invalid_credentials  
- timeout  
- market_closed  
- symbol_unavailable  
- permission_denied  
- not_connected  
- probe_error  

## APIs (additive)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/broker-connectivity/certification` | Status |
| GET | `/broker-connectivity/certification/dashboard` | Dashboard |
| GET | `/broker-connectivity/certification/history` | History |
| POST | `/broker-connectivity/certification/run` | Run against live MT5 |

## UI

`/broker-certification` — desk dashboard (same primitives as compatibility; not a redesign of existing pages).

## How to certify

1. Connect broker MT5 via `/mt5` with the exact portal server.  
2. Ensure paper engine is registered for full path to Certified.  
3. POST `/broker-connectivity/certification/run` (or UI button).  
4. Only the **matched** brand can reach Certified; others stay Pending Session.

## Related

- `BROKER_COMPATIBILITY_REPORT.md`  
- `BROKER_CONNECTIVITY.md`  
- Live MT5: `/mt5/*`
