# QuantForg Closed Beta — Production Audit Report

**Date:** 2026-07-15  
**Baseline commit:** `9074a00294272a35759fa106fd58e2365afbc238`  
**Scope:** Closed Beta readiness only — **no new major product modules**  
**Constraint:** Locked desks (Gateway, Broker Workspace, Trading Terminal, OMS, Execution Engine, Decision Engine, Quant AI, Quant Studio, Research Lab, Auth, TradingSessionProvider, Portfolio/Execution Intelligence, Risk Engine, existing APIs) were **not modified**.

---

## Architecture (Closed Beta surface)

```
Invite / Maintenance / Read-only gates
        │
        ▼
Next.js App Shell (auth layout)  ──►  /api/v1/* (FastAPI)
        │                                      │
        ├─ Overview desks (Dashboard, Quant*)  ├─ EXECUTION_ENABLED=false (prod forced)
        ├─ Trading desks (Broker, Terminal)    ├─ Security headers + CORS allowlist
        ├─ Research desks (Studio, Lab, DE)    ├─ Auth rate limit (in-process)
        └─ Ops (/ops, /cloud-ops)              └─ Gateway token (server→Windows only)
                                                      │
                                                      ▼
                                            MT5 Windows Gateway
                                            (credentials in-memory)
```

Data policy: no fabricated market data; advisory desks never `order_send`.

---

## Phase 1 — Production audit (pages)

| Surface | Route | Status | Notes |
|---------|-------|--------|-------|
| Dashboard | `/dashboard` | Pass | RQ + DeskSkeleton/Error/Empty + SessionStrip |
| Portfolio | `/portfolio` | Pass | Same desk pattern |
| Wallet | `/wallet` | Pass* | Missing DeskEmpty |
| Orders / Positions / History | `/orders` `/positions` `/history` | Pass | Full desk primitives |
| Broker Workspace | `/broker` | Pass* | Custom errors; redirects from `/mt5` `/brokers` |
| Trading Terminal / Execution | `/workspace` `/execution` | Pass* | Dynamic WorkspaceShell |
| Execution Intelligence | `/execution-intel` | Pass* | DeskError; no DeskEmpty |
| Quant AI / Studio / Decision Engine / Research Lab | respective routes | Pass | Advisory flags + EXECUTION_ENABLED badge |
| Settings / Profile / Notifications / Orgs | account routes | Pass | RQ desks |
| Operations | `/ops` | Pass | Admin-gated dashboard/metrics/alerts/audit |
| Cloud Ops | `/cloud-ops` | Pass | Gateway HA / heartbeats |
| Support / Get Started / What’s New | `/support` `/get-started` `/whats-new` | Pass | Onboarding surfaces |
| Health / Diagnostics | `/health` `/health/live` `/health/ready` + Support | Pass | Public probes |
| Admin | *(none)* | N/A | No `/admin`; use `/ops` owner/admin RBAC |

\*Acceptable for Closed Beta; polish tracked as Minor.

**E2E coverage:** 21 Playwright tests across auth, institutional desk, Quant AI/Studio/DE/Research Lab. Gaps: ops, cloud-ops, wallet/orders/history, many research auxiliaries — **Major** for broad GA, acceptable under invite beta with operator smoke.

---

## Phase 2 — UX audit

| Check | Finding | Severity |
|-------|---------|----------|
| Loading states | Most desks use `DeskSkeleton`; WorkspaceShell has import skeleton | Minor gaps: `/ai`, `/risk` |
| Empty states | 17 pages use `DeskEmpty`; 21 lack it | Minor |
| Error messages | 29 desks use `DeskError`; broker/workspace use toasts | Minor |
| Mobile | MobileNav drawer with aria; sidebar `hidden lg:flex` | Pass |
| Keyboard / a11y | Terminal `role="application"`, tablists, collapse aria-labels; primary nav labeled | Pass for beta |
| Dark mode | Desk CSS variables; institutional dark surfaces consistent | Pass |
| Performance UX | Shared RQ defaults (30s stale); desk-specific poll budgets | Pass |

---

## Phase 3 — Security audit

| Control | Verdict |
|---------|---------|
| Authentication | Supabase JWT Bearer — **Pass** for beta |
| Authorization | Route deps + ops owner/admin — **Pass** |
| Secrets | Prod rejects insecure markers; `.env.example` documented — **Pass** |
| Broker credentials | Windows gateway memory only; never Railway/browser policy — **Pass (ops discipline)** |
| Gateway tokens | Server-side `MT5_GATEWAY_CALLER_TOKEN` — **Pass** |
| CORS | Explicit origins, no `*` with credentials — **Pass** |
| Security headers | nosniff, DENY frame, HSTS on HTTPS, no-store — **Pass** |
| Rate limits | Auth endpoints 30/60s **in-process** — **Major** (multi-replica) |
| Live execution | Default + production force `EXECUTION_ENABLED=false` — **Pass / Critical control** |
| Token storage | `localStorage` Bearer — **Major** XSS residual (documented) |

---

## Phase 4 — Performance audit

| Metric | Observed / documented | Notes |
|--------|----------------------|-------|
| Unit suite | 444 passed (~9s) | Local gate |
| Frontend build output | `.next` ~37M; static ~4.3M; ~89 chunk files | Post-build 2026-07-15 |
| React Query | Global stale 30s; desks 8–120s; poll 20–60s on hot paths | Shared keys on Quant* / Lab |
| API TTL caches | Quant AI 15s, DE 12s, Studio 20s, Lab 25s | Reduces duplicate MT5 analysis |
| DB latency | ~180–220ms cross-region floor (prior report) | Colocate for GA |
| Gateway latency | Cloudflare 522/523/524 classified; heartbeats on `/cloud-ops` | Ops-visible |

Duplicate polling: residual across desks with overlapping MT5 status — acceptable for beta with SessionStrip; consolidating sessions is **locked** (TradingSessionProvider).

---

## Phase 5 — Reliability audit

| Failure mode | Expected recovery | Beta posture |
|--------------|-------------------|--------------|
| Gateway restart | Passwordless attach + reconnect manager; `/cloud-ops` shows heartbeat gaps | Operator verifies |
| Railway restart | Unprefixed `/health` probes; sticky process restart | Auto via platform |
| Cloudflare reconnect | Client timeout mapping; tunnel rebind | Ops check gateway URL |
| MT5 disconnect | Gateway reconnect if enabled; Weltrade reconnect API | Paper-first guidance |
| Broker reconnect | `/weltrade/reconnect`, broker health APIs | No password round-trip to browser |
| Network loss | Client errors + DeskError; no invented quotes | Pass |

Formal chaos automation is **not** in CI — reliability verified via code paths + runbooks + operator drills. Tracked as Major before public GA.

---

## Issues register

### Critical
1. **Unsupervised live trading** — Must keep `EXECUTION_ENABLED=false` and paper-first messaging. *(Control exists; operational Critical.)*

### Major
1. Bearer tokens in `localStorage` (XSS session risk).  
2. In-process auth rate limits (not shared across replicas).  
3. Incomplete Playwright coverage for ops / wallet / order book routes.  
4. Cross-region Postgres latency floor.  
5. Ops alerts not wired to mandatory on-call (webhook optional).  
6. No automated gateway/Railway chaos suite.

### Minor
1. DeskEmpty gaps (wallet, analytics, settings, etc.).  
2. `/ai` and `/risk` lack full desk primitives.  
3. No dedicated `/admin` console (ops is sufficient for beta).  
4. Frontend CSP still allows unsafe-inline/eval (prior cert).

---

## Risk matrix

| Risk | Likelihood | Impact | Mitigation | Residual |
|------|------------|--------|------------|----------|
| Accidental live send | Low | Critical | Prod forces EXECUTION_ENABLED off; UI read-only flag | Low |
| Credential leakage | Low | Critical | Gateway-only passwords; audit policy | Low |
| Session theft via XSS | Med | High | Invite cohort; CSP/headers; short TTL | Med |
| Gateway outage | Med | High | Reconnect + paper fallback + maintenance mode | Med |
| Rate-limit bypass under scale | Low–Med | Med | Invite-only traffic; rotate invite | Med |
| User confusion (paper vs live) | Med | Med | Onboarding + What’s New + badges | Low–Med |

---

## Go / No-Go

### Recommendation: **GO — Closed Beta (conditional)**

**Conditions (must hold before invitees land):**

1. `EXECUTION_ENABLED=false` verified in Railway.  
2. `NEXT_PUBLIC_BETA_MODE=true` + invite code distributed.  
3. No broker passwords in Railway/browser env.  
4. At least one live Windows gateway registered **or** paper-only cohort acknowledged.  
5. `/ops` owner monitoring + feedback channel (webhook or email) active.  
6. What’s New updated for build containing Research Lab (`9074a00`).

**Not GO for:** unsupervised live trading, public open beta, or GA without Major mitigations above.

---

## Production readiness

| Dimension | Closed Beta | Public GA |
|-----------|-------------|-----------|
| Core platform complete | Yes | Yes |
| Advisory intelligence suite | Yes | Yes |
| Live execution | No (gated off) | Supervised only |
| Ops observability | Yes (`/ops`) | Needs pager wiring |
| Security residual | Acceptable under invite | HttpOnly / shared RL required |
| Decision | **GO conditional** | **NO GO** until Majors closed |
