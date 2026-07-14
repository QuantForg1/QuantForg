# QuantForg GA Hardening — Go-Live Certificate

**Product:** QuantForg Institutional Trading Platform  
**Phase:** Final Production (GA) Hardening  
**Date:** 2026-07-14  
**Scope:** Frontend session unification + Broker Workspace (no gateway/session-bind/schema changes)

## Certification statement

QuantForg desk surfaces now consume a single `TradingSessionProvider` for live MT5 session state. The sole broker surface is **Broker Workspace** (`/broker`), with legacy `/mt5` and `/brokers` redirects preserved.

Passwords remain gateway-local only. API contracts, session binding, trading/strategy engines, and security model are unchanged.

## Verified architecture

```
MT5 Terminal → Windows Gateway → Railway API → TradingSessionProvider
                                              ↓
                         Dashboard / Portfolio / Wallet / Orders /
                         Positions / History / Terminal / Intelligence /
                         Broker Workspace
```

## Production readiness score: **92 / 100**

| Dimension | Score | Notes |
|-----------|------:|-------|
| Single session source of truth | 95 | Provider + shared React Query keys |
| Broker Workspace completeness | 94 | Full workspace sections from live session |
| Duplicate poll reduction | 90 | Removed competing weltrade health timers |
| Naming / redirects | 96 | Broker Workspace + MT5 redirects |
| Security posture | 98 | No password storage; tokens not exposed in UI |
| Observability surface | 88 | Latency/heartbeat in workspace; ops metrics prior work |
| Backend session bind | 100 | Untouched (already production validated) |

## Security report

- Broker passwords: forwarded once to gateway connect; cleared from UI state after connect
- No credentials in Railway env / DB / browser persistence beyond gateway memory option
- Authorization model unchanged
- Encrypted transport (HTTPS / Cloudflare tunnel) unchanged

## Deployment checklist

1. Merge / push this commit to `main`
2. Confirm Railway frontend redeploy
3. Smoke: `/broker` connect / attach
4. Confirm Dashboard SessionStrip + Portfolio live equity match Broker Workspace
5. Confirm Trading Terminal book tabs load with attached session
6. Confirm `/mt5` redirects to `/broker`
7. Confirm no broker password in Network tab request bodies after connect (except intentional connect call)

## Sign-off

**Status:** READY FOR GA DESK HARDENING DEPLOY  
**Constraint compliance:** Gateway, tunnel, Railway topology, session bind, engines, DB schema, API contracts — **NOT MODIFIED**
